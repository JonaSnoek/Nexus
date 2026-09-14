# NEXUS - SSO/OIDC Configuration

NEXUS supports external Single Sign-On (SSO) via OIDC, which is compatible with
Authentik, Keycloak, and other OIDC providers.

## 1. Global flags

Enable OIDC in `.env`:

```dotenv
OIDC_ENABLED=true
OIDC_ISSUER_URL=https://your-provider.example/application/o/nexus/
OIDC_CLIENT_ID=nexus
OIDC_CLIENT_SECRET=replace-me
OIDC_REDIRECT_URI=https://nexus.example.com/auth/callback
```

When `OIDC_ENABLED=false`, login page shows the normal username/password form.
When `OIDC_ENABLED=true`, the login page shows a "Sign in with SSO" button as the
primary action (local accounts are still available in the admin panel).

## 2. Role mapping

Roles come from the `groups` claim (an array of group name strings):

| .env variable        | Default    | Meaning                                  |
|----------------------|------------|------------------------------------------|
| `OIDC_GROUP_ADMINS`  | `admins`   | Users in this group get role `ADMIN`     |
| `OIDC_GROUP_USERS`   | `users`    | Users in this group get role `USER`      |

Sync behavior:
- Unknown SSO users are created automatically on first login (role from group mapping).
- If a user is in neither group, they get `USER` (no external role leakage to ADMIN).
- Group changes on the provider take effect on the user's next login.

## 3. Minimum provider requirements

The provider must support:
- OpenID Connect discovery (`.well-known/openid-configuration`)
- Authorization Code flow with PKCE off (NEXUS uses client secret)
- A `groups` claim (or you must map it at the provider)

## 4. Authentik

See `oidc-authentik.md`.

## 5. Keycloak

See `oidc-keycloak.md`.