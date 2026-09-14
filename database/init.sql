-- NEXUS - PostgreSQL initialization script
-- Runs inside the postgres container on first boot (docker-entrypoint-initdb.d)
-- Auth is handled by the backend (bcrypt); pgcrypto is optional for future use.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- The nexus user/database are created by the POSTGRES_* env vars in docker-compose.
-- Nothing else is required for a fresh install; migrations are applied by alembic.