# NEXUS - SSO with Keycloak

## Create the realm client

1. Keycloak Admin Console -> Realm -> Clients -> Create.
   - Client ID: `nexus`
   - Client type: `Confidential`
2. In the client settings:
   - **Valid redirect URIs**: `https://nexus.example.com/auth/callback`
   - **Valid post logout redirect URIs**: `https://nexus.example.com`
3. Copy the **Client secret** from the Credentials tab.
4. Save the realm's issuer URL:
   `https://auth.example.com/realms/<REALM_NAME>`

## Client scopes / claims

Make sure the `groups` claim is included. In most Keycloak setups the
`groups` claim is part of the default `profile` scope, otherwise:

1. Client Scopes -> Create (e.g. `groups`).
2. Add a Mapper of type "Group Membership":
   - Token Claim Name: `groups`
   - Claim JSON Type: `String`
   - Add to ID token: `ON`
   - Add to access token: `ON`
3. Assign the scope to the `nexus` client.

Create realm roles or groups named `admins` / `users` (or whatever you set in
`OIDC_GROUP_ADMINS` / `OIDC_GROUP_USERS`) and assign users.

## .env

```dotenv
OIDC_ENABLED=true
OIDC_ISSUER_URL=https://auth.example.com/realms/nexus
OIDC_CLIENT_ID=nexus
OIDC_CLIENT_SECRET=<client-secret>
OIDC_REDIRECT_URI=https://nexus.example.com/auth/callback
OIDC_GROUP_ADMINS=admins
OIDC_GROUP_USERS=users
```

## Notes

- NEXUS performs OIDC discovery against the issuer URL, so the authorization /
  token / userinfo endpoints are resolved automatically.
- Keycloak must be reachable from the NEXUS container (and browser).
- Only the `groups` claim is read; `email` (if present) and `preferred_username`
  are used to fill the user account.