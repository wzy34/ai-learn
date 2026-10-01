from fastapi import APIRouter
from app.models.common import HealthResponse
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint

    Returns:
        HealthResponse with service status
    """
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment="development" if settings.DEBUG else "production"
    )
