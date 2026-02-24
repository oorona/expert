# System Configuration & Secrets

This project uses Docker environment variables and Docker Secrets to securely run the applications.

## Secrets Management

Security is paramount. The system explicitly avoids storing plain-text keys in `docker-compose.yml`.

Ensure the following files exist locally before deploying, as they are securely mounted into the containers during runtime under `/run/secrets/`:
*   `secrets/api_key.txt`: Base HTTP Basic internal proxy connection key for frontend-to-backend authorization.
*   `secrets/db_password.txt`: The postgres password for accessing your external Database. (**Important**: Though the external DB is remote, the docker-compose expects this secret to exist to authorize local clients mapping DB URLs).
*   `secrets/gemini_api_key.txt`: Your Google Gemini SDK Token.

## Environment Variables
The application utilizes a `.env` file at the root of the project to drive all dynamic configurations, ensuring no URLs or structural components are hardcoded into the `docker-compose.yml`.

Copy the provided `.env.example` file and configure it for your deployment environment:

```bash
cp .env.example .env
```

### `backend`
*   `POSTGRES_USER`: Target database username (e.g., `expert`).
*   `POSTGRES_DB`: Target database name (e.g., `expert`).
*   `POSTGRES_HOST`: The FQDN or IP of your external PostgreSQL server. Ensure this database exists prior to starting the service.

### `frontend`
*   `INTERNAL_API_URL`: Controls how the Next.js `app/api/...` routes proxy traffic internally to FastAPI over the `intranet` Docker network. Defaults to `http://expert-backend:8000`. Do not change this unless modifying Docker network topologies.
*   `NODE_ENV`: Should be `production` for optimized React builds.

## Traefik Reverse Proxy Config
The `docker-compose.yml` configures the frontend to be available externally via a Traefik proxy on the `internet` network.
*   It exposes the frontend using the `${DOMAIN}` environment variable (e.g., `DOMAIN=expert.home.iktdts.com`).
*   It automatically applies `tls=true` and sets the entrypoint to `websecure`.
*   Note: The backend is intentionally isolated alongside the frontend in the `intranet` network and is **not** exposed to Traefik directly. All external traffic is routed via Next.js server-side API endpoints contextually to ensure maximum security.
