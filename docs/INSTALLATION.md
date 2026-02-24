# Installation & Quick Start

This guide will walk you through setting up the AI Diagnostic Engine on your local machine or server.

## Prerequisites

Ensure you have the following installed on your host machine:
- **Docker** and **Docker Compose**
- **Traefik** Reverse Proxy (configured with an `internet` network)
- **External PostgreSQL 18** database (with `pgvector` and `pg_textsearch` extensions installed)
- **Google Gemini API Key**

## Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/expert-diagnostic-engine.git
   cd expert-diagnostic-engine
   ```

2. **Configure your Database**
   Ensure your external PostgreSQL instance has an empty database named `expert` and a user named `expert` with appropriate privileges. The backend application will automatically create all tables and perform necessary schema migrations upon startup using Alembic. You **do not** need to manually deploy the tables.

3. **Configure Secrets & Environment**
   Please see the [Configuration Guide](CONFIGURATION.md) to set up your `.env` variables and Docker Secrets (for API keys and database passwords).

4. **Deploy the Application**
   ```bash
   export POSTGRES_HOST=your.external.db.hostname
   export DOMAIN=expert.yourdomain.com
   docker compose up -d --build
   ```

5. **Verify the Deployment**
   Once the containers are running securely behind Traefik, access the Next.js frontend at the domain you specified:
   `https://$DOMAIN`

## Quick Start
1. Log in to the application and navigate to the **Admin Dashboard -> Expert Manager**.
2. Click **Create Expert**. Input a name (e.g., "Kubernetes Expert") and a brief description. The AI will autonomously generate appropriate prompts for this domain.
3. Upload any relevant technical documentation to the newly created Expert to populate the Vector Search database (RAG).
4. Return to the main Dashboard, select your expert, and submit an error stack trace or dashboard screenshot to begin diagnosing!
