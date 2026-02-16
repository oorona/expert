import asyncio
import logging
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from db.session import async_session, engine
from db.init import seed_defaults
from routers import admin, chat, diagnose, documents, experts, images, incidents, ingest, search
from services.gemini import gemini_service
from services.similarity import normalize_error_text

logger = logging.getLogger(__name__)

MAX_DB_RETRIES = 30
DB_RETRY_DELAY = 2  # seconds


async def _wait_for_db():
    """Block until PostgreSQL is accepting connections."""
    for attempt in range(1, MAX_DB_RETRIES + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database is ready.")
            return
        except Exception as exc:
            logger.warning(
                "DB not ready (attempt %d/%d): %s", attempt, MAX_DB_RETRIES, exc
            )
            await asyncio.sleep(DB_RETRY_DELAY)

    raise RuntimeError(
        f"Could not connect to the database after {MAX_DB_RETRIES} attempts"
    )


def _run_alembic_subprocess(command_name: str, revision: str = "head"):
    """Execute an Alembic command in an isolated subprocess.

    Using a subprocess avoids the deadlock that occurs when
    ``asyncio.run()`` (in Alembic's async env.py) is called inside a
    thread spawned by ``loop.run_in_executor()`` — asyncpg cleanup
    can hang indefinitely in that scenario.
    """
    import os
    import sys

    env = os.environ.copy()
    # Ensure the app directory is importable in the child process.
    env.setdefault("PYTHONPATH", os.path.dirname(__file__) or ".")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", command_name, revision],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__) or ".",
        env=env,
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            logger.info("alembic: %s", line)
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            logger.info("alembic: %s", line)
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic {command_name} failed (exit {result.returncode}): "
            f"{result.stderr}"
        )


async def _run_migrations():
    """Detect legacy schemas and run Alembic migrations."""
    loop = asyncio.get_event_loop()

    try:
        async with engine.connect() as conn:
            has_alembic = await conn.scalar(
                text(
                    "SELECT EXISTS "
                    "(SELECT 1 FROM information_schema.tables "
                    " WHERE table_name = 'alembic_version')"
                )
            )
            has_tables = await conn.scalar(
                text(
                    "SELECT EXISTS "
                    "(SELECT 1 FROM information_schema.tables "
                    " WHERE table_name = 'incidents')"
                )
            )

        # Legacy DB: tables exist but Alembic hasn't been initialised yet.
        if has_tables and not has_alembic:
            logger.info("Legacy database detected — stamping with initial migration …")
            await loop.run_in_executor(
                None, _run_alembic_subprocess, "stamp", "0001"
            )

        logger.info("Running database migrations …")
        await loop.run_in_executor(
            None, _run_alembic_subprocess, "upgrade", "head"
        )
        logger.info("Database migrations complete.")
    except Exception:
        logger.exception("Failed to run database migrations")
        raise


async def _reembed_incidents():
    """Re-embed all incidents using normalised error text.

    This ensures the stored embedding matches the same normalisation
    applied to incoming queries, making duplicate detection reliable.
    Runs once per startup but skips incidents that already have the
    ``embedding_version`` flag set to 2.
    """
    try:
        async with async_session() as session:
            rows = await session.execute(
                text(
                    "SELECT id, error_text FROM incidents "
                    "WHERE error_text IS NOT NULL AND error_text != '' "
                    "AND (embedding_version IS NULL OR embedding_version < 2)"
                )
            )
            to_update = rows.fetchall()
            if not to_update:
                logger.info("All incident embeddings are up-to-date.")
                return
            logger.info("Re-embedding %d incidents with normalised text …", len(to_update))
            for row in to_update:
                normalised = normalize_error_text(row.error_text)
                embedding = await gemini_service.generate_embedding(normalised)
                emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
                await session.execute(
                    text(
                        "UPDATE incidents SET embedding = CAST(:emb AS vector), "
                        "embedding_version = 2 WHERE id = :id"
                    ),
                    {"emb": emb_str, "id": row.id},
                )
            await session.commit()
            logger.info("Re-embedding complete.")
    except Exception as e:
        logger.error(
            "Failed to re-embed incidents due to database error: %s\n"
            "This may indicate database corruption. Consider running:\n"
            "  docker exec -it expert-db psql -U postgres -d expert\n"
            "  REINDEX TABLE incidents;\n"
            "  VACUUM FULL incidents;",
            e
        )
        logger.warning("Skipping re-embedding. Application will continue to start.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. Wait until the database is reachable
    await _wait_for_db()

    # 1. Run Alembic migrations (handles fresh + legacy + incremental)
    await _run_migrations()

    # 2. Seed default prompts / schemas if missing
    async with async_session() as session:
        await seed_defaults(session)
        await session.commit()

    # 3. Initialise external services
    await gemini_service.initialize()

    # 4. One-time: re-embed incidents using normalised error text
    await _reembed_incidents()

    yield

    await engine.dispose()


app = FastAPI(lifespan=lifespan, title="Expert Diagnostic Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4100",
        "http://expert-frontend:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "X-Client-Key"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )

app.include_router(diagnose.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api")
app.include_router(experts.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(search.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "healthy"}
