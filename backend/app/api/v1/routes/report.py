from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import AuthenticatedUser, get_optional_current_user
from app.models.common import APIResponse
from app.models.report import ReportCreateRequest, ReportResponse
from app.services.report_service import get_report_service
from app.services.learning_record_service import get_learning_record_service
from app.core.exceptions import QuizAppException
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/report", tags=["Report"])


@router.post("/generate", response_model=APIResponse[ReportResponse])
async def generate_report(
    request: ReportCreateRequest,
    current_user: Annotated[
        AuthenticatedUser | None,
        Depends(get_optional_current_user),
    ],
):
    """Generate learning report from quiz results

    Args:
        request: Report creation request with quiz data and answer records

    Returns:
        APIResponse with generated report data

    Raises:
        HTTPException: If report generation fails
    """
    try:
        logger.info("Report generation request", quiz_id=request.quiz_id)

        report_service = get_report_service()
        response = await report_service.generate_report(request)

        if current_user is not None:
            await get_learning_record_service().save_completed_quiz(
                user_id=current_user.user_id,
                request=request,
                report=response,
            )

        logger.info("Report generated successfully", accuracy=response.accuracy)

        return APIResponse(code=0, message="Report generated successfully", data=response)

    except QuizAppException as e:
        logger.warning("Report generation failed (app error)", detail=e.detail)
        raise HTTPException(status_code=e.status_code, detail={"code": -1, "message": e.detail})

    except Exception as e:
        logger.error("Report generation failed (unexpected error)", error=str(e))
        raise HTTPException(status_code=500, detail={"code": -1, "message": "Internal server error"})


@router.get("/health")
async def report_health():
    """Report service health check"""
    return {"status": "ok", "service": "report"}
