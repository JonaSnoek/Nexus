from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password, get_password_hash, get_current_active_user
from app.models.user import User, UserRole, UserPermission, Permission
from app.schemas.auth import LoginRequest, TokenResponse, SetupRequest
from app.services.user_service import create_user, get_user_by_username, get_monthly_summary
from app.services.settings_service import get_sso_settings, sso_enabled
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _normalize_role(user: User) -> str:
    return user.role.value.lower() if isinstance(user.role, UserRole) else str(user.role).lower()


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(db, body.username)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(data={"sub": str(user.id), "username": user.username, "role": _normalize_role(user)})

    client_ip = request.client.host if request.client else None
    await log_action(db, "login", user_id=user.id, details=f"User {user.username} logged in", ip_address=client_ip)

    return TokenResponse(access_token=token)


@router.post("/setup", response_model=TokenResponse)
async def setup(body: SetupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()
    if user_count and user_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setup already completed")

    user = await create_user(
        db,
        username=body.username,
        password=body.password,
        email=body.email,
        display_name=body.display_name,
        role="ADMIN",
    )

    token = create_access_token(data={"sub": str(user.id), "username": user.username, "role": "admin"})
    return TokenResponse(access_token=token)


@router.get("/oidc/authorize")
async def oidc_authorize(db: AsyncSession = Depends(get_db)):
    sso = await get_sso_settings(db)
    if not sso["oidc_enabled"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC not configured")
    import urllib.parse
    params = urllib.parse.urlencode({
        "client_id": sso["oidc_client_id"],
        "redirect_uri": sso["oidc_redirect_uri"],
        "response_type": "code",
        "scope": "openid profile email",
    })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"{sso['oidc_issuer_url']}/protocol/openid-connect/auth?{params}")


@router.get("/oidc/callback")
async def oidc_callback(code: str, db: AsyncSession = Depends(get_db)):
    sso = await get_sso_settings(db)
    if not sso["oidc_enabled"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC not configured")

    import httpx
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            f"{sso['oidc_issuer_url']}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": sso["oidc_redirect_uri"],
                "client_id": sso["oidc_client_id"],
                "client_secret": sso["oidc_client_secret"],
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC token exchange failed")
        token_data = token_resp.json()

        userinfo_resp = await client.get(
            f"{sso['oidc_issuer_url']}/protocol/openid-connect/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC userinfo failed")
        userinfo = userinfo_resp.json()

    username = userinfo.get("preferred_username", userinfo.get("sub", ""))
    email = userinfo.get("email", "")
    display_name = userinfo.get("name", username)

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user:
        user.last_login = datetime.now(timezone.utc)
        user.email = email
        user.display_name = display_name
        await db.commit()
    else:
        groups = userinfo.get("groups", [])
        role = "ADMIN" if sso["oidc_group_admins"] in groups else "USER"
        user = await create_user(
            db,
            username=username,
            password="",
            email=email,
            display_name=display_name,
            role=role,
            is_sso=True,
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    client_ip = None
    await log_action(db, "oidc_login", user_id=user.id, details=f"OIDC login for {username}", ip_address=client_ip)

    token = create_access_token(data={"sub": str(user.id), "username": user.username, "role": _normalize_role(user)})
    return TokenResponse(access_token=token)


@router.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    perms_result = await db.execute(
        select(Permission.name)
        .join(UserPermission, UserPermission.permission_id == Permission.id)
        .where(UserPermission.user_id == current_user.id)
    )
    permissions = [p for p in perms_result.scalars().all()]

    if current_user.role == UserRole.ADMIN:
        all_perms = await db.execute(select(Permission.name))
        permissions = list(set(permissions) | set(all_perms.scalars().all()))

    usage = await get_monthly_summary(db, current_user)

    return {
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "email": current_user.email,
        "role": _normalize_role(current_user),
        "is_active": current_user.is_active,
        "is_sso": current_user.is_sso,
        "monthly_token_limit": current_user.monthly_token_limit,
        "monthly_message_limit": current_user.monthly_message_limit,
        "period": usage["period"],
        "tokens_used_month": usage["tokens_used_month"],
        "messages_used_month": usage["messages_used_month"],
        "tokens_remaining_month": usage["tokens_remaining_month"],
        "messages_remaining_month": usage["messages_remaining_month"],
        "permissions": permissions,
    }