# NEXUS - Self-Hosted AI Assistant

NEXUS is a modern, self-hosted AI assistant platform designed to run entirely on your own hardware. It combines a local LLM backend (Ollama) with a polished web interface, complete user management, single sign-on, an admin dashboard, and an image-generation architecture — all packaged for Docker-based deployment.

```
┌───────────────────────────────────────────────────────────────┐
│  NEXUS                                                         │
│  Self-hosted, private, and fully under your control.            │
│  Your data never leaves your infrastructure.                    │
└───────────────────────────────────────────────────────────────┘
```

---

## Features

- **Local AI chat with streaming** — token-by-token streaming responses powered by [Ollama](https://ollama.com). No third-party API calls, no data leaving your machine.
- **User management with roles and permissions** — create users, assign granular permissions, activate/deactivate accounts, and inspect per-user usage.
- **SSO via OpenID Connect (OIDC)** — drop-in integration with self-hosted identity providers such as [Authentik](https://goauthentik.io/), Keycloak, and any OIDC-compatible provider.
- **Admin dashboard with system monitoring** — live counts of users, chats, messages, and token usage, plus CPU/memory/disk/uptime reporting and Ollama model management.
- **Quota & limits system (per month)** — drei Zustände pro Benutzer (Standardlimit / benutzerdefiniert / unbegrenzt), serverseitig atomar durchgesetzt (race-condition-sicher). Pro Aktion (Chat-Nachricht, Bildgenerierung) wird ein konfigurierbarer Token-Verbrauch vom Kontingent abgezogen; ein transparenter Usage-Ledger zeichnet jeden Verbrauch auf.
- **Audit logging** — every sensitive action (logins, user creation, permission changes, chat deletion) is recorded with actor, IP, and timestamp.
- **Responsive dark-themed UI** — a fast, keyboard-friendly React frontend styled for long chat sessions.
- **Docker-based deployment** — every service ships as a container; one `docker compose up` brings the whole stack online.
- **Automated installation** — a single `install.sh` script checks prerequisites, installs Docker, generates secrets, pulls your model, and health-checks the result.

---

## Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS          | Linux x86_64 | Linux x86_64 (Ubuntu 22.04 / Debian 12 / Fedora 39) |
| RAM         | 4 GB | 16 GB |
| CPU         | 2 cores | 8 cores |
| Disk        | 10 GB free | 50 GB+ free (LLM models are large) |
| Docker      | 20.10+ | Latest stable |
| Docker Compose | v2 (plugin) | v2 (plugin) |
| GPU (optional) | — | NVIDIA GPU with CUDA for accelerated inference |

> On Windows/macOS you can still run NEXUS with Docker Desktop for development, but the automated installer and the recommended production path target **Linux x86_64**. For NVIDIA GPU acceleration you must also install the `nvidia-container-toolkit` (see [LLM Configuration](#llm-configuration)).

---

## Installation

```bash
git clone https://github.com/JonaSnoek/Nexus.git
cd Nexus
sudo ./install.sh
```

Der Installer ist **idempotent** (mehrfaches Ausfuehren ist sicher) und **daten-erhaltend**. Er:

1. Prueft Root-Rechte, Linux und x86_64.
2. Prueft den Speicherplatz (`df /`). Sind weniger als 3 GB frei, wird nur der **ungenutzte Docker-Build-Cache** entfernt (`docker builder prune -af`). **Es werden niemals Volumes geloescht.**
3. Installiert Docker und Docker Compose falls fehlend.
4. Erstellt `.env` aus `.env.example` und generiert starke Secrets (JWT-Key, PostgreSQL-Passwort).
5. Fragt das Admin-Passwort ab (leer = spaeter in `.env` setzen).
6. Gibt Port 80 in der Firewall (UFW/firewalld) frei, falls aktiv.
7. Erkennt das PostgreSQL-Volume: **existiert es bereits, werden die bestehenden Daten verwendet**; eine neue Datenbank wird nur initialisiert, wenn kein Volume existiert.
8. Baut die Images (mit Docker-Cache – kein `--no-cache`), startet PostgreSQL, wartet auf Health, synchronisiert das Datenbank-Schema (Alembic), startet Backend.
9. Laedt das LLM-Modell in Ollama (kann mehrere Minuten dauern).
10. Startet alle Container und testet `http://SERVER-IP/api/health`.

## Zugriff

Nach der Installation im Browser:

```
http://SERVER-IP
```

Ohne Port. `SERVER-IP` ermittelt der Installer automatisch und gibt sie aus. Login: `admin` / dein Admin-Passwort.

Zusaetzlich laeuft NEXUS auf dem Caddy Reverse Proxy an **Port 80**, der intern alle `/api/`-Requests an das Backend und alle anderen an das Frontend weiterleitet. Backend, PostgreSQL und Ollama sind **nicht** direkt aus dem Netzwerk erreichbar (keine Port-Veröffentlichung).

> **Benötigte Ports:** nur **80** (HTTP). **443** wird nur geoeffnet, wenn du spaeter HTTPS via `config/Caddyfile.production` aktivierst. Keine weiteren Ports werden nach aussen veroeffentlicht.

> Optional spaeter via Domain + **Cloudflare Tunnel**: Cloudflare Tunnel benoetigt keinen offenen Port und kein Cloudflare-Plugin im NEXUS-Container. Tunnel einfach auf den Server-Port 80 (oder 443) zeigen lassen (z.B. `cloudflared tunnel --url http://localhost`). Die lokale IP-Version `http://SERVER-IP` funktioniert dabei **unabhaengig** von Cloudflare weiter.

## Update

```bash
cd /opt/nexus
sudo ./update.sh
```

Das Skript:

1. Prueft den Speicherplatz (entfernt bei Bedarf automatisch nur den ungenutzten Docker-Build-Cache).
2. Sichert die `.env` als `.env.bak-<Zeitstempel>`.
3. Fuehrt `git pull` aus.
4. Baut und startet Container via `docker compose up -d --build` – **es werden niemals Volumes entfernt** (`docker compose down -v` wird nie verwendet), Chatverlaeufe, Benutzer, Einstellungen und Datenbank bleiben erhalten.
5. Fuehrt Datenbankmigrationen aus (`alembic upgrade head`; bei bereits aktueller DB nur `stamp head`).
6. Waertet Healthchecks ab und prueft, ob NEXUS wieder erreichbar ist.
7. Schlaegt das Update fehl, wird automatisch auf den vorherigen Commit zurueckgesetzt und neu gestartet.

## Reparatur

```bash
cd /opt/nexus
sudo ./repair.sh
```

Diagnostiziert und repariert eine bestehende Installation **ohne Daten zu loeschen**:

- Speicher, Docker, Compose-Datei und Container-Status pruefen.
- PostgreSQL prüfen und das PostgreSQL-Volume identifizieren (bestehende Daten bleiben unangetastet).
- Bei Speichermangel nur den ungefaehrlichen Docker-Build-Cache bereinigen.
- NEXUS starten und Healthchecks + Port-80-Pruefung durchfuehren.

Beispielausgabe:

```
  Disk:        OK
  Docker:      OK
  Compose:     OK
  PostgreSQL:  OK
  Backend:     OK
  Frontend:    OK
  Ollama:      OK
  HTTP (Port 80): OK

  NEXUS:       http://192.168.2.100
```

## Rollback

```bash
cd /opt/nexus
sudo ./rollback.sh
```

Setzt den letzten Git-Commit zurueck, stellt die `.env` aus dem letzten Update-Backup wieder her und startet die Container neu. **Es werden keine Datenbankdaten geloescht.**

## Installation: Speicher & Ports

| Anforderung | Minimum |
|-------------|---------|
| Speicher (`df /`) | min. **3 GB frei** vor Installation/Update |
| Ports | **80** (HTTP). 443 nur fuer spaetere HTTPS-Domain |
| Docker-Build-Cache | wird **nur** bei Speichermangel automatisch bereinigt (`docker builder prune -af`) |
| Gefaehrliche Befehle | `docker compose down -v`, `docker system prune --volumes`, `docker volume rm` - **werden nie automatisch ausgefuehrt** |

## Installationsort & Daten

| Was | Wo |
|-----|----|
| Repository | `/opt/nexus` (bzw. der Ordner, in dem geklont wurde) |
| Konfiguration | `/opt/nexus/.env` |
| Datenbank (PostgreSQL) | Docker-Volume `nexus-postgres-data` |
| LLM-Modelle (Ollama) | Docker-Volume `nexus-ollama-data` |
| TLS-Zertifikate (Caddy) | Docker-Volumes `caddy-data`, `caddy-config` |
| Backups | `/opt/nexus/backups/` (Host-Dateisystem, **nicht** in einem Docker-Volume) |

**Wichtig:** Die Docker-Volumes enthalten alle Ihre Daten. Der normale Update-/Repair-Prozess fasst sie niemals an. Ein Backup ist daher der einzige Weg, Daten dauerhaft zu sichern (siehe [Backup & Restore](#backup--restore)).

Details siehe [Manual Installation](#manual-installation) und [Backup & Restore](#backup--restore).

---

## Manual Installation

If you prefer to run the steps yourself, or you are on a machine that already has Docker configured:

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-org/nexus.git
   cd nexus
   ```

2. **Create and edit the environment file**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and, at minimum, set:

   - The JWT signing secret (a long random string used to sign tokens).
   - `POSTGRES_PASSWORD` — used by the PostgreSQL container and `DATABASE_URL`.
   - `FIRST_ADMIN_PASSWORD` — so the admin user is created on first boot.

   Generate strong values with:

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. **Build the images**

   ```bash
   docker compose build
   ```

4. **Start PostgreSQL first and wait for it to become healthy**

   ```bash
   docker compose up -d postgres
   docker inspect --format='{{.State.Health.Status}}' nexus-postgres   # wait for "healthy"
   ```

5. **Start the backend, then Ollama**

   ```bash
   docker compose up -d nexus-backend ollama
   ```

   The backend creates all database tables automatically on startup.

6. **Pull your LLM model** (default `qwen3:8b`)

   ```bash
   docker exec nexus-ollama ollama pull qwen3:8b
   ```

7. **Start every service**

   ```bash
   docker compose up -d
   ```

8. **Verify**

   ```bash
   curl -s http://localhost/api/health
   # {"status":"ok","database":"ok","ollama":"ok"}
   ```

9. **Log in** — open `http://localhost` and sign in as `admin` with your `FIRST_ADMIN_PASSWORD`.

---

## Configuration

Copy `.env.example` to `.env` and adjust what you need. All variables are read at container startup — restart the backend after changing them.

### Application / Backend

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Secret used to sign JWT access tokens. Generate a long random value. The bundled `.env.example` names it `NEXUS_SECRET_KEY` — the installer writes one for you. | random 32 bytes |
| `ALGORITHM` | JWT signing algorithm. | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Lifetime of a login token, in minutes. | `60` |
| `DATABASE_URL` | SQLAlchemy async database URL used by the backend. | `postgresql+asyncpg://nexus:nexus@postgres:5432/nexus` |
| `NEXUS_PORT` | Port NEXUS is configured to listen on for local development. | `3000` |
| `OLLAMA_URL` | Base URL of the Ollama API from the backend container's perspective. | `http://ollama:11434` |
| `NEXUS_LLM_MODEL` | Default LLM model used for chat. See [LLM Configuration](#llm-configuration). | `qwen3:8b` |
| `IMAGE_PROVIDER` | Image generation backend architecture (`none` for now; providers plug in here). | `none` |
| `FIRST_ADMIN_USERNAME` | Username of the admin account created on first boot. | *(empty — set at install)* |
| `FIRST_ADMIN_PASSWORD` | Password for that admin account. You can also use the `/api/auth/setup` endpoint instead. | *(empty)* |
| `FIRST_ADMIN_EMAIL` | Email address for that admin account. | *(empty)* |

### Database (Docker)

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_DB` | Name of the NEXUS database. | `nexus` |
| `POSTGRES_USER` | PostgreSQL user. | `nexus` |
| `POSTGRES_PASSWORD` | PostgreSQL password. **Must be set** — used by both the `postgres` container and `DATABASE_URL`. | *(required)* |

### SSO (OIDC)

| Variable | Description | Default |
|----------|-------------|---------|
| `OIDC_ENABLED` | Enable or disable OIDC SSO. | `false` |
| `OIDC_ISSUER_URL` | Base URL of your identity provider (e.g. `https://auth.example.com`). | *(empty)* |
| `OIDC_CLIENT_ID` | Client ID created in the identity provider. | *(empty)* |
| `OIDC_CLIENT_SECRET` | Client secret created in the identity provider. | *(empty)* |
| `OIDC_REDIRECT_URI` | Callback URI that the provider should redirect to. | `http://localhost/auth/callback` |
| `OIDC_GROUP_ADMINS` | Provider group whose members become NEXUS admins. | `admins` |
| `OIDC_GROUP_USERS` | Provider group whose members become regular NEXUS users. | `users` |

### Backup

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKUP_DIR` | Directory where `backup.sh` stores archives. | `./backups` |

---

## SSO Configuration

NEXUS implements OpenID Connect the standard way: it can be configured with any OIDC provider. The steps below use Authentik as the example.

### 1. Create a provider in Authentik

1. Log in to your Authentik admin interface.
2. Go to **Applications → Providers → Create**.
3. Choose **OAuth2/OpenID Provider**.
4. Enter a name (e.g. `NEXUS`), leave `Authorization flow` unset, and set:
   - **Client Type**: `Confidential`
   - **Redirect URIs**: `http://your-nexus-host/auth/callback` (must match `OIDC_REDIRECT_URI`)
5. Save and copy the generated **Client ID** and **Client Secret**.

### 2. Create an application in Authentik

1. Go to **Applications → Applications → Create**.
2. Name it `NEXUS` and attach the provider you just created.
3. Save.

### 3. Create groups (optional but recommended)

1. Under **Directory → Groups**, create `admins` and `users`.
2. Assign your admin users to `admins`, everyone else to `users`.

### 4. Configure NEXUS environment variables

```ini
OIDC_ENABLED=true
OIDC_ISSUER_URL=https://auth.example.com
OIDC_CLIENT_ID=your-authentik-client-id
OIDC_CLIENT_SECRET=your-authentik-client-secret
OIDC_REDIRECT_URI=http://your-nexus-host/auth/callback
OIDC_GROUP_ADMINS=admins
OIDC_GROUP_USERS=users
```

Restart the backend after making the change:

```bash
docker compose restart nexus-backend
```

### 5. Group mapping

When a user authenticates with SSO for the first time, NEXUS looks them up by their `preferred_username` (OpenID Connect claims). If the user is not found they are created automatically. Group membership determines their role:

- Member of `OIDC_GROUP_ADMINS` → `ADMIN`
- Member of `OIDC_GROUP_USERS` (or no group match) → `USER`

### 6. Testing SSO

1. Visit `http://your-nexus-host/api/auth/oidc/authorize` — you will be redirected to Authentik.
2. Sign in with a test account.
3. You will be redirected back and issued a NEXUS token.
4. Confirm the account was created under **Users** in the NEXUS admin panel.

---

## Quota & Limits

NEXUS erfasst pro Benutzer ein **monatliches Token-Kontingent** und ein **monatliches Nachrichten-Limit**. Ein Token ist das interne NEXUS-Kontingent (unabhängig von den Provider-Token-Zählern von Ollama, die zusätzlich als Metadaten gespeichert werden).

### Die drei Zustände pro Benutzer

| Zustand | Konfiguration | Effekt |
|---------|---------------|--------|
| **Standard** | `limits_exempt=false` | Benutzer nutzt das globale Standard-Limit aus den Einstellungen. |
| **Benutzerdefiniert** | `limits_exempt=true` + `custom_monthly_token_limit` | Benutzer erhält ein festes eigenes Kontingent. |
| **Unbegrenzt** | `limits_exempt=true` + `unlimited=true` | Benutzer wird nie blockiert; der Verbrauch wird trotzdem erfasst (Statistik/Transparenz). |

Ungültige Kombinationen werden serverseitig normalisiert (z. B. wird `unlimited=true` automatisch mit `custom_monthly_token_limit=null` verknüpft). Das Frontend entscheidet **nie** über die Zugriffslogik – die Durchsetzung geschieht ausschließlich im Backend.

### Token-Verbrauch pro Aktion

| Einstellung | Standard | Beschreibung |
|-------------|----------|--------------|
| `default_token_limit` | `100` | Globales Standard-Kontingent pro Monat (für Neuinstallationen). |
| `default_message_limit` | `1000` | Globales Nachrichten-Limit pro Monat. |
| `chat_message_cost` | `1` | Tokens, die jede Chat-Nachricht vom Kontingent abzieht. |
| `image_generation_cost` | `10` | Tokens, die eine Bildgenerierung vom Kontingent abzieht. |

> **Wichtig:** Bestehende Datenbanken behalten ihre eingetragenen Werte. Der neue Standard (`100`) gilt nur, wenn kein Eintrag existiert. Die Kosten werden pro Aktion **atomar** gebucht (ein einzelner UPSERT mit Guard) – parallele Anfragen können das Kontingent nie gemeinsam überschreiten. Bei erschöpfendem Kontingent antwortet die API mit `429` und `detail.error_code="LIMIT_REACHED"`.

**Speicherung:** Chats und Nachrichten werden **dauerhaft** pro Benutzer in PostgreSQL gespeichert (zugeordnet über die `user_id` des Chats). Es gibt keine automatische Löschung oder Ablaufzeit – gelöscht wird nur, wenn ein Benutzer einen Chat/eine Nachricht explizit über die UI oder API entfernt.

### Verbrauch-Seite (Admin)

- **Benutzerliste & Limits bearbeiten:** Admin → Users. Drei Zustände als Umschalter, individuelle Kontingente und Nachrichtenlimits pro Benutzer.
- **`GET /api/admin/usage/summary`** liefert pro Benutzer Limit, Verbrauch, Rest, Verbrauch heute, Aktionen und Gesamtsummen des aktuellen Monats.
- **`GET /api/admin/users/{id}/limits`** gibt den vollständigen Limit-Zustand eines Benutzers zurück.
- **`GET /api/users/{id}/usage/events`** liefert den lückenlosen Usage-Ledger (jede Buchung mit Aktion, Tokens und Zeitstempel).

---

## LLM Configuration

NEXUS talks to Ollama, which pulls and runs open-weight models locally. The model is chosen with the `NEXUS_LLM_MODEL` environment variable.

### 1. Set the model

```ini
NEXUS_LLM_MODEL=qwen3:8b
```

or override it for a single request by sending a custom `model` in the message body:

```json
{
  "content": "Explain quantum computing in simple terms",
  "model": "llama3.1:8b"
}
```

### 2. Pull models into Ollama

```bash
# with docker
docker exec nexus-ollama ollama pull llama3.1:8b

# or via the admin API
curl -X POST http://localhost/api/admin/models/pull \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.1:8b"}'
```

### Available models

`Ollama Model Library` has hundreds of models. Common choices:

| Model | Parameter count | RAM (CPU) | Notes |
|-------|-----------------|-----------|-------|
| `qwen3:4b` | 4B | ~3-4 GB | Fast, low-footprint default for 8 GB hosts |
| `qwen3:8b` | 8B | ~6-8 GB | **Default** — best balance of quality and speed |
| `llama3.1:8b` | 8B | ~6-8 GB | Excellent general-purpose tooling model |
| `mistral:7b` | 7B | ~5-7 GB | Fast and strong at instruction following |
| `gemma2:9b` | 9B | ~7-9 GB | Google's compact Gemini-style model |
| `deepseek-r1:7b` | 7B | ~6-8 GB | Reasoning-focused model |
| `llama3.3:70b` | 70B | ~40+ GB | High-quality; needs serious hardware |

Run `docker exec nexus-ollama ollama list` to see what is already present on your host.

### RAM requirements

LLM memory usage is roughly the parameter count scaled by the quantization precision. As a rule of thumb, reserve **~1 GB of RAM per 1B parameters** for CPU inference at default quantization, plus ~2 GB for the rest of the stack. On a 4 GB host stick to small models (`qwen3:4b`); for interactive use of 8B models plan for 16 GB.

### CPU vs GPU

- **CPU only**: works out of the box — Ollama on CPU is correct but slower (a few tokens/second for 8B models).
- **NVIDIA GPU (CUDA)**: install the `nvidia-container-toolkit`, then add to `docker-compose.yml`:

  ```yaml
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  ```

  and restart:

  ```bash
  docker compose up -d ollama
  ```

  Ollama automatically detects the GPU and offloads inference to it.
- **AMD / Apple Silicon**: Ollama supports these too; enable the relevant Ollama flags in the service environment.

---

## Backup & Restore

### Backup

```bash
sudo bash backup.sh
```

This creates a timestamped archive in `./backups` (override with `BACKUP_DIR`) containing:

- a `pg_dump` of the PostgreSQL database (`database.sql.gz`),
- your `.env` file (so secrets travel with the backup),
- the `docker-compose.yml` and `docker-compose.prod.yml` files,
- your `config/` directory.

Example output:

```
  Location: backups/nexus-backup-20260914-091530.tar.gz
```

### Restore

```bash
sudo bash restore.sh                              # lists backups and prompts
sudo bash restore.sh backups/nexus-backup-20260914-091530.tar.gz
```

The restore script:

1. Stops all containers.
2. Drops and recreates the database, then imports `database.sql.gz`.
3. Restores `.env` and `config/`.
4. Starts all services and runs a health check.

> **Warning**: restore overwrites the current database and configuration. It asks you to confirm with `yes` before touching anything.

### Automating backups with cron

```bash
# Nightly at 03:00
0 3 * * * cd /opt/nexus && sudo bash backup.sh
# Clean up backups older than 30 days
30 3 * * * find /opt/nexus/backups -name '*.tar.gz' -mtime +30 -delete
```

---

## Update

```bash
sudo bash update.sh
```

The updater:

1. Stops all containers while preserving storage volumes.
2. Pulls the latest code with `git pull`.
3. Rebuilds all images with `--no-cache` to avoid stale layers.
4. Starts PostgreSQL, waits for it to be healthy, then starts the backend.
5. Refreshes your configured Ollama model (`ollama pull`).
6. Starts everything and runs a health check.

> Tip: run `bash backup.sh` before updating so you can roll back if needed.

---

## Uninstall

```bash
sudo bash uninstall.sh
```

The uninstaller stops and removes all NEXUS containers, then asks three questions:

| Prompt | What it removes |
|--------|-----------------|
| `Remove database volumes` | `nexus-postgres-data`, `nexus-ollama-data`, `caddy-data`, `caddy-config` (**deletes all data**) |
| `Remove Docker images` | The `nexus-frontend` / `nexus-backend` images and dangling images |
| `Remove backup archives` | Everything in `BACKUP_DIR` |

If you answer **no** to any prompt, the corresponding artifacts are preserved and the script prints the manual commands to remove them later.

---

## Architecture

NEXUS is composed of five containers orchestrated by Docker Compose on a private `nexus-network` bridge:

```
                        ┌────────────────────────┐
                        │        Browser         │
                        │      (dark UI)         │
                        └───────────┬────────────┘
                                    │ HTTP/HTTPS (80 / 443)
                                    ▼
                        ┌────────────────────────┐
                        │        Caddy           │  Reverse proxy + TLS
                        │    :80   :443          │
                        └───────────┬────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌──────────────────────┐          ┌──────────────────────┐
        │    Frontend          │ /api/*   │    Backend           │
        │   React + Nginx      │─────────▶│   FastAPI  :8000     │
        │   static SPA :80     │          │   business logic     │
        └──────────────────────┘          └──────┬───────┬───────┘
                                                 │       │ async ORM
                                                 │       ▼
                                                 │  ┌──────────────┐
                                                 │  │  PostgreSQL  │
                                                 │  │ :5432 (vol)  │
                                                 │  └──────────────┘
                                                 ▼
                                        ┌──────────────────────┐
                                        │      Ollama          │
                                        │ LLM :11434 (vol)    │
                                        │ chat + generate     │
                                        └──────────────────────┘
```

### Services

| Service | Role | Ports |
|---------|------|-------|
| **Frontend** (`nexus-frontend`) | React SPA (Vite build) served by Nginx. Proxies `/api/*` to the backend. | `80` (published) |
| **Backend** (`nexus-backend`) | FastAPI application. Auth, users, chat, permissions, admin, health, audit logging. Serves the API and streams LLM tokens via SSE. | `8000` (internal) |
| **PostgreSQL** (`postgres`) | Primary datastore — users, permissions, chats, messages, usage, audit logs. Data persisted in the `nexus-postgres-data` volume. | `5432` (internal) |
| **Ollama** (`ollama`) | Local LLM inference engine. Models persisted in the `nexus-ollama-data` volume. | `11434` (internal) |
| **Caddy** (`caddy`) | Edge reverse proxy and automatic HTTPS termination. | `80`, `443` (published) |

The backend talks to Ollama over the internal network using `httpx`. Chat responses are returned as Server-Sent Events (`text/event-stream`) so tokens appear as they are generated.

For production-like resource limits and log rotation, layer `docker-compose.prod.yml` on top:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## API Reference

Base URL: `http://localhost` (via Caddy) or `http://localhost:8000` (backend directly).

All endpoints except `/api/auth/login`, `/api/auth/setup`, `/api/setup/*`, `/api/health`, and `/` require a `Bearer` token:

```
Authorization: Bearer <access_token>
```

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Log in with username/password, returns a JWT |
| `POST` | `/api/auth/setup` | First-run admin creation (must be the first user) |
| `GET` | `/api/auth/me` | Current user profile |
| `GET` | `/api/auth/oidc/authorize` | Redirect to the OIDC provider's login |
| `POST` | `/api/auth/oidc/callback` | OIDC code exchange and login |

```bash
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
# {"access_token":"eyJhbGciOi...","token_type":"bearer"}
```

### Setup

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/setup/status` | Whether an initial setup is still required |
| `POST` | `/api/setup/` | Complete initial setup (creates the first admin) |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/chat/` | List the current user's chats |
| `POST` | `/api/chat/` | Create a chat |
| `GET` | `/api/chat/{id}` | Chat detail including all messages |
| `PUT` | `/api/chat/{id}` | Rename a chat |
| `DELETE` | `/api/chat/{id}` | Delete a chat |
| `POST` | `/api/chat/{id}/messages` | Send a message; returns an SSE stream of tokens |
| `POST` | `/api/chat/{id}/messages/{message_id}/regenerate` | Regenerate an assistant message |
| `DELETE` | `/api/chat/{id}/messages/{message_id}` | Delete a message |

```bash
# create a chat
curl -X POST http://localhost/api/chat/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "My first chat"}'

# send a message (streams SSE tokens)
curl -N -X POST http://localhost/api/chat/1/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello NEXUS"}'
```

### Users (admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users/` | List all users |
| `POST` | `/api/users/` | Create a user |
| `GET` | `/api/users/{id}` | Get a user |
| `PUT` | `/api/users/{id}` | Update a user (name, email, role, active) |
| `DELETE` | `/api/users/{id}` | Deactivate a user |
| `PUT` | `/api/users/{id}/permissions` | Replace a user's permission set |
| `PUT` | `/api/users/{id}/limits` | Set a user's quota (standard / custom / unlimited) |
| `GET` | `/api/users/{id}/usage` | Last 30 days of usage for a user |
| `GET` | `/api/users/{id}/usage/events` | Usage ledger entries for a user (admin or the user themself) |

### Permissions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/permissions/` | List all known permissions (any authenticated user) |
| `POST` | `/api/permissions/` | Create a permission (admin) |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/dashboard` | System counters (users, chats, messages, tokens today) |
| `GET` | `/api/admin/logs` | Audit log entries (filter by `user_id` / `action`) |
| `GET` | `/api/admin/system` | CPU, memory, disk, uptime |
| `GET` | `/api/admin/models` | Installed Ollama models |
| `POST` | `/api/admin/models/pull` | Pull a model into Ollama |
| `GET` | `/api/admin/models/status` | Ollama health + default model presence |
| `GET` | `/api/admin/settings/limits` | Default limits and action costs (token/message limit, chat/image cost) |
| `PUT` | `/api/admin/settings/limits` | Update the default limits and action costs |
| `GET` | `/api/admin/users/{id}/limits` | Limit state + current-period usage for one user |
| `GET` | `/api/admin/usage/summary` | Per-user quota summary for the current month |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Overall health: `status`, `database`, `ollama` |

```bash
curl -s http://localhost/api/health
# {"status":"ok","database":"ok","ollama":"ok"}
```

---

## Permissions

NEXUS users have a role (`ADMIN` or `USER`) and an optional set of fine-grained permissions. **Admins implicitly hold every permission** — they bypass permission checks entirely.

The following permissions are seeded automatically with a fresh install:

| Permission | Description |
|------------|-------------|
| `chat.use` | Use the chat feature and send messages |
| `chat.manage` | Rename, delete, and organize chats |
| `image.generate` | Generate images via the image provider |
| `admin.access` | Access the admin panel and admin APIs |

Additional permissions can be created from the admin panel or via `POST /api/permissions/`. Assignment is done with `PUT /api/users/{id}/permissions`:

```json
{
  "permission_ids": [1, 3]
}
```

Role behavior summary:

| Capability | ADMIN | USER |
|------------|-------|------|
| Chat | ✔ | ✔ (with permissions) |
| Manage own users/chats | ✔ | ✔ |
| View / create permissions | ✔ any | ✔ read-only |
| Manage any user | ✔ | ✘ |
| Admin dashboard, logs, system info | ✔ | ✘ |
| Pull Ollama models | ✔ | ✘ |
| Bypass permission checks | ✔ | ✘ |

---

## Development

### Backend setup

Requires Python 3.11+.

```bash
cd backend

# create a virtualenv and install dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# install test dependencies
pip install pytest pytest-asyncio aiosqlite
```

Run the backend locally against SQLite (no Docker required):

```bash
# Windows PowerShell
$env:DATABASE_URL = "sqlite+aiosqlite:///./dev.db"
$env:FIRST_ADMIN_USERNAME = "admin"
$env:FIRST_ADMIN_PASSWORD = "admin"

# Linux/macOS
# export DATABASE_URL="sqlite+aiosqlite:///./dev.db"

uvicorn app.main:app --reload --port 8000
```

Or against PostgreSQL via Docker:

```bash
docker compose up -d postgres
cd backend
uvicorn app.main:app --reload --port 8000
```

Open the interactive docs at `http://localhost:8000/docs` (Swagger UI) to try every endpoint.

### Frontend setup

Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to the backend; see `vite.config.ts` for the proxy target. Build a production bundle with `npm run build` (outputs to `frontend/dist`).

### Running tests

The test suite uses `pytest` with `pytest-asyncio` and runs against an isolated SQLite database. Ollama and all external services are mocked — **no Docker, database, or network access required**.

```bash
# from the repository root (pytest.ini sets asyncio_mode=auto)
pytest tests -v

# or run a single file
pytest tests/test_auth.py -v
```

The common fixtures live in `tests/conftest.py` (a copy is mirrored at `backend/tests/conftest.py` so tests can also live alongside the backend package).

Test coverage by file:

| File | Covers |
|------|--------|
| `tests/test_auth.py` | Login, setup, `/me`, token expiry |
| `tests/test_users.py` | CRUD, permissions, limits, deactivation |
| `tests/test_chat.py` | Chat CRUD, streaming messages, quota enforcement |
| `tests/test_limits.py` | Three-state quota system, atomic charges, race conditions, month switch, permissions |
| `tests/test_permissions.py` | Permission checks and listing |
| `tests/test_health.py` | Health endpoint, setup status |
| `tests/test_admin.py` | Dashboard, audit logs, system info |

---

## Troubleshooting

### Container won't start

```bash
docker compose ps                 # is it there? what state?
docker compose logs <service>     # "nexus-frontend", "nexus-backend", ...
```

**Backend crashes on boot?** A missing or malformed `.env` is the most common cause. Verify required variables exist (`POSTGRES_PASSWORD`, secret key) and that `DATABASE_URL` matches `POSTGRES_PASSWORD`. If you changed `.env`, remove the container and start fresh:

```bash
docker compose down
docker compose up -d
```

**Frontend returns 502?** The frontend waits for the backend's healthcheck. Give it a few seconds, then `docker compose ps` — if the backend is `unhealthy`, check its logs.

**Frontend is `unhealthy`?** The container's healthcheck uses `curl -fsS http://localhost/`. `curl` is installed into the production image (`RUN apk add --no-cache curl`). Cause of the healthcheck failing:

```bash
docker logs --tail=30 nexus-frontend           # nginx errors / curl not found?
docker exec nexus-frontend curl -fsS http://localhost/ && echo OK   # internal test
docker inspect nexus-frontend --format='{{json .State.Health}}'     # last health output
```

Wenn der Container mit einer **alten Version** laeuft (vor dem curl-Einbau), hilft ein Rebuild:
```bash
sudo ./repair.sh           # baut das Frontend-Image neu (mit Cache) und startet es
```
**Wichtig:** Caddy wartet auf `nexus-frontend service_healthy`. Ist das Frontend nicht `healthy`, startet Caddy nicht und Port 80 ist tot. Die Ursache muss also behoben, nicht der Healthcheck deaktiviert werden.

### Disk full / No space left on device

Symptom: `FATAL: could not write lock file "postmaster.pid"`, container restart loops, `docker compose up` fails mid-build.

**1. Diagnose:**
```bash
df -h /
docker system df
```

**2. Gefahrlos bereinigen (beruehrt KEINE Daten):**
```bash
docker builder prune -af        # nur ungenutzter Build-Cache
docker image prune -af          # nur unbenutzte/dangling Images
```

**3. Reparieren und pruefen:**
```bash
sudo ./repair.sh                # bereinigt Build-Cache, startet Stack, Healthchecks
```

**Niemals** `docker compose down -v`, `docker system prune --volumes` oder `docker volume rm` verwenden - das wuerde die Datenbank und die Chatverlaeufe loeschen.

### Database connection failed

```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection failed
```

1. Ensure PostgreSQL is healthy: `docker inspect --format='{{.State.Health.Status}}' nexus-postgres`.
2. Confirm `POSTGRES_PASSWORD` in `.env` matches the password inside `DATABASE_URL`:

   ```ini
   POSTGRES_PASSWORD=MySecret
   DATABASE_URL=postgresql+asyncpg://nexus:MySecret@postgres:5432/nexus
   ```

3. Verify the database volume survived: `docker volume ls | grep nexus-postgres`.

### Ollama not responding

1. Check the container: `docker compose ps ollama` and `docker compose logs ollama`.
2. Try the API directly: `curl -s http://localhost:11434/api/tags` (host) or `docker exec nexus-ollama curl -s http://localhost:11434/api/tags` (inside the container).
3. On NAT-ed / firewalled hosts make sure `OLLAMA_URL` is reachable from the *backend* container, not just the host.
4. If a chat returns `[unable to load model]`, pull the model: `docker exec nexus-ollama ollama pull qwen3:8b`.

### Out of memory

Ollama loads the entire model into RAM. If the host OOMs:

- Switch to a smaller model (`NEXUS_LLM_MODEL=qwen3:4b`).
- Check free memory: `free -h`.
- Confirm the container memory limits (`docker compose.prod.yml` caps Ollama at 8 GB).
- Set a smaller context window in Ollama's `options` if you access the raw API.

### Permission denied

**`Permission denied` running the scripts?** Make them executable:

```bash
chmod +x install.sh backup.sh restore.sh update.sh uninstall.sh healthcheck.sh
sudo bash install.sh     # the install/uninstall/restore scripts must run as root
```

**Docker permission denied** — add your user to the `docker` group and re-login:

```bash
sudo usermod -aG docker $USER
```

**Port 80 already in use** — Caddy needs port 80/443. Free it, or change the published ports in `docker-compose.yml`.

---

## Security

NEXUS is designed for self-hosting with security in mind:

- **Password storage** — bcrypt hashing via `passlib`; plaintext passwords are never stored or logged.
- **JWT authentication** — stateless bearer tokens signed with `HS256` using a server-side `SECRET_KEY`; tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60 minutes).
- **Role-based access control** — admin endpoints (users, permissions, logs, system info) reject non-admin callers with `403`, and chats are scoped per user so one user can never read another's data.
- **Per-user quotas** — monthly token and message limits (standard / custom / unlimited per user) enforced atomically in the backend; even unlimited accounts keep reporting their usage.
- **Audit logging** — logins, user creation, permission changes, chat deletions, and OIDC logins are recorded with actor, IP, and timestamp for post-incident review.
- **SSO-ready** — OIDC integration lets you centralize identity with Authentik/Keycloak instead of managing passwords in NEXUS.
- **TLS by default** — Caddy terminates HTTPS with automatic certificates, so traffic to the browser is encrypted.
- **Sandboxed services** — each component runs in its own container; only Caddy and the frontend expose public ports, keeping PostgreSQL and Ollama off the host network.

### Best practices

1. **Change all default secrets** — the installer generates them, but if you created `.env` manually, replace the signing secret and `POSTGRES_PASSWORD`.
2. **Keep `.env` out of git** — it is already git-ignored; never commit it.
3. **Use HTTPS** — put NEXUS behind Caddy (or your own reverse proxy) and enable automatic certificate renewal.
4. **Restrict the admin group** — with SSO, only members of the admin group should be granted `ADMIN`.
5. **Back up regularly** — schedule `backup.sh` and test a `restore.sh` on a scratch instance before you need it.
6. **Stay updated** — run `update.sh` to receive fixes; rebuilds pick up the latest base images.
7. **Harden the host** — apply OS patches, use a firewall that only exposes 80/443, and consider `docker-compose.prod.yml` for resource limits.

---

## License

MIT © NEXUS Contributors. See [LICENSE](LICENSE) for the full text.