from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_permission
from app.models.user import User, UserRole, GeneratedImage
from app.providers.images import ImageGenerationError
from app.schemas.image import ImageGenerateRequest, GeneratedImageResponse
from app.services.image_service import generate_image, image_file_path, serialize_image

router = APIRouter(prefix="/api/images", tags=["images"])


async def _get_image(
    db: AsyncSession,
    current_user: User,
    image_id: int,
) -> GeneratedImage:
    result = await db.execute(select(GeneratedImage).where(GeneratedImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bild nicht gefunden.")
    # Only the owner (or an admin) may access the image.
    if image.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kein Zugriff auf dieses Bild.",
        )
    return image


@router.post(
    "/generate",
    response_model=GeneratedImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_image_generation(
    body: ImageGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image.generate")),
):
    try:
        image, _message = await generate_image(
            db, current_user, body.prompt, body.chat_id, body.model, body.size
        )
    except ImageGenerationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": exc.message,
                "error_code": exc.error_code or "IMAGE_GENERATION_ERROR",
            },
        )
    return serialize_image(image)


@router.get("/{image_id}", response_model=GeneratedImageResponse)
async def get_image_metadata(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image.generate")),
):
    image = await _get_image(db, current_user, image_id)
    return serialize_image(image)


@router.get("/{image_id}/file")
async def get_image_file(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("image.generate")),
):
    image = await _get_image(db, current_user, image_id)
    path = image_file_path(image)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bilddatei nicht gefunden.")
    return FileResponse(path, media_type="image/png")