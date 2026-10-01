from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.db import database
from app.core.logging import setup_logging, get_logger
from app.api.v1.routes import health, quiz, report, user

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting application", app_name=settings.APP_NAME, version=settings.APP_VERSION)
    yield
    await database.close()
    logger.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Quiz Learning Backend API",
    lifespan=lifespan
)


# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(quiz.router, prefix="/api/v1")
app.include_router(report.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")


# Serve uploaded avatars (see app/services/avatar_storage.py)
Path(settings.AVATAR_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/static/avatars", StaticFiles(directory=settings.AVATAR_UPLOAD_DIR), name="avatars")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": -1, "message": "Internal server error", "data": None}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
