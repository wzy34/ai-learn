from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import AuthenticatedUser, get_optional_current_user, get_required_current_user
from app.models.common import APIResponse
from app.models.quiz import DrillCreateRequest, QuizCreateRequest, QuizResponse
from app.services.quiz_service import get_quiz_service
from app.services.learning_record_service import get_learning_record_service
from app.services.weak_point_service import get_weak_point_service
from app.core.exceptions import QuizAppException
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])

DRILL_USER_INPUT_TEMPLATE = (
    "我正在专项突破薄弱知识点「{focus}」。"
    "请围绕这个知识点出题，重点考查它的核心概念、常见误区和易错点，"
    "帮助我通过闯关答题针对性巩固。"
)


def _drill_title(generated_title: str) -> str:
    """Mark drill sessions so they are recognisable in history lists."""

    return f"专项训练 · {generated_title}"[:250]


@router.post("/generate", response_model=APIResponse[QuizResponse])
async def generate_quiz(
    request: QuizCreateRequest,
    current_user: Annotated[
        AuthenticatedUser | None,
        Depends(get_optional_current_user),
    ],
):
    """Generate quiz from user input

    Args:
        request: Quiz creation request with user_input and optional parameters

    Returns:
        APIResponse with generated quiz data

    Raises:
        HTTPException: If quiz generation fails
    """
    try:
        logger.info("Quiz generation request", user_input=request.user_input[:100])

        quiz_service = get_quiz_service()
        response = await quiz_service.generate_quiz(request)

        if current_user is not None:
            await get_learning_record_service().save_generated_quiz(
                user_id=current_user.user_id,
                request=request,
                quiz=response,
            )

        logger.info("Quiz generated successfully", quiz_id=response.quiz_id)

        return APIResponse(code=0, message="Quiz generated successfully", data=response)

    except QuizAppException as e:
        logger.warning("Quiz generation failed (app error)", detail=e.detail)
        raise HTTPException(status_code=e.status_code, detail={"code": -1, "message": e.detail})

    except Exception as e:
        logger.error("Quiz generation failed (unexpected error)", error=str(e))
        raise HTTPException(status_code=500, detail={"code": -1, "message": "Internal server error"})


@router.post("/drill", response_model=APIResponse[QuizResponse])
async def generate_drill_quiz(
    request: DrillCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
):
    """Generate a targeted quiz for one of the caller's weak knowledge points.

    When `focus` is omitted, the user's most frequent weak point from recent
    reports is used. The drill is always persisted so it can be continued.
    """
    try:
        focus = (request.focus or "").strip()
        if not focus:
            summary = await get_weak_point_service().get_weak_points(
                current_user.user_id
            )
            if not summary.items:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": 404,
                        "message": "暂无可训练的薄弱点，先完成一次闯关生成报告吧",
                    },
                )
            focus = summary.items[0].point

        quiz_request = QuizCreateRequest(
            user_input=DRILL_USER_INPUT_TEMPLATE.format(focus=focus),
            question_count=request.question_count,
            difficulty="mixed",
        )
        response = await get_quiz_service().generate_quiz(quiz_request)
        response = response.model_copy(update={"title": _drill_title(response.title)})

        await get_learning_record_service().save_generated_quiz(
            user_id=current_user.user_id,
            request=quiz_request,
            quiz=response,
        )

        logger.info(
            "Drill quiz generated successfully",
            quiz_id=response.quiz_id,
            focus=focus,
        )
        return APIResponse(code=0, message="Drill quiz generated successfully", data=response)

    except QuizAppException as e:
        logger.warning("Drill generation failed (app error)", detail=e.detail)
        raise HTTPException(status_code=e.status_code, detail={"code": -1, "message": e.detail})

    except HTTPException:
        # Intentional client-facing errors (e.g. no weak points yet) keep
        # their original status and message.
        raise

    except Exception as e:
        logger.error("Drill generation failed (unexpected error)", error=str(e))
        raise HTTPException(status_code=500, detail={"code": -1, "message": "Internal server error"})


@router.get("/health")
async def quiz_health():
    """Quiz service health check"""
    return {"status": "ok", "service": "quiz"}
