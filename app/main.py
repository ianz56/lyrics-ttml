"""
Lyrics TTML API Server

FastAPI application that serves TTML lyrics as structured data.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.songs import router as songs_router, search_router


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Lyrics TTML API",
        description=(
            "API server for TTML (Timed Text Markup Language) lyric files. "
            "Provides endpoints to browse, search, and import lyrics with "
            "word-level timing, background vocals, translations, and romanization."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow all in development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(songs_router)
    app.include_router(search_router)

    @app.get("/", tags=["health"])
    async def root():
        return {
            "name": "Lyrics TTML API",
            "version": "1.0.0",
            "docs": "/docs",
        }

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
