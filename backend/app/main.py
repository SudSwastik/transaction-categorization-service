from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routers import auth as auth_router
from app.api.v1.routers import statements as statements_router
from app.core.config import get_settings
from app.observability.logging import setup_logging
from app.services.storage_service import get_storage_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(log_level=settings.LOG_LEVEL, environment=settings.ENVIRONMENT)
    get_storage_service().ensure_bucket()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Transaction Categorization API",
        version=settings.VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.VERSION}

    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(statements_router.router, prefix="/api/v1")

    return app


app = create_app()
