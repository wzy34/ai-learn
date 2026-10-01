from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.core.auth import AuthenticatedUser, get_required_current_user
from app.core.exceptions import QuizAppException
from app.models.common import APIResponse
from app.models.quiz import QuizResponse
from app.models.user import (
    LoginRequest,
    LoginResponse,
    QuizHistoryDetail,
    QuizHistoryPage,
    UnfinishedQuizList,
    UpdateProfileRequest,
    UserProfile,
    WeakPointSummary,
)
from app.services.history_service import get_history_service
from app.services.user_service import get_user_service
from app.services.weak_point_service import get_weak_point_service

router = APIRouter(prefix="/user", tags=["User"])


def _raise_user_error(error: QuizAppException) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.status_code, "message": error.detail},
    )


@router.post("/login", response_model=APIResponse[LoginResponse])
async def login(request: LoginRequest) -> APIResponse[LoginResponse]:
    """Sign in with a WeChat login code and return an application token."""

    try:
        response = await get_user_service().login_with_code(request.code)
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="Login successful", data=response)


@router.get("/profile", response_model=APIResponse[UserProfile])
async def get_profile(
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
) -> APIResponse[UserProfile]:
    """Return the caller's profile and completed-learning aggregates."""

    try:
        profile = await get_user_service().get_profile(current_user.user_id)
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="Profile retrieved successfully", data=profile)


@router.put("/profile", response_model=APIResponse[UserProfile])
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
) -> APIResponse[UserProfile]:
    """Update the caller's supported profile fields."""

    try:
        profile = await get_user_service().update_profile(current_user.user_id, request)
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="Profile updated successfully", data=profile)


@router.post("/avatar", response_model=APIResponse[UserProfile])
async def upload_avatar(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
) -> APIResponse[UserProfile]:
    """Store an uploaded image and set it as the caller's avatar."""

    content = await file.read()
    try:
        profile = await get_user_service().update_avatar(current_user.user_id, content)
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="Avatar updated successfully", data=profile)


@router.get("/quizzes", response_model=APIResponse[QuizHistoryPage])
async def list_quizzes(
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> APIResponse[QuizHistoryPage]:
    """List the caller's completed quizzes from newest to oldest."""

    try:
        history = await get_history_service().list_quizzes(
            current_user.user_id,
            page,
            page_size,
        )
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="History retrieved successfully", data=history)


@router.get("/quizzes/unfinished", response_model=APIResponse[UnfinishedQuizList])
async def list_unfinished_quizzes(
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> APIResponse[UnfinishedQuizList]:
    """List the caller's generated-but-unfinished quizzes from newest to oldest."""

    try:
        unfinished = await get_history_service().list_unfinished_quizzes(
            current_user.user_id,
            limit,
        )
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(
        code=0,
        message="Unfinished quizzes retrieved successfully",
        data=unfinished,
    )


@router.get("/quizzes/{quiz_id}", response_model=APIResponse[QuizHistoryDetail])
async def get_quiz_detail(
    quiz_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
) -> APIResponse[QuizHistoryDetail]:
    """Return a completed quiz only when it belongs to the caller."""

    try:
        history = await get_history_service().get_quiz_detail(
            current_user.user_id,
            quiz_id,
        )
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="History detail retrieved successfully", data=history)


@router.get("/quizzes/{quiz_id}/resume", response_model=APIResponse[QuizResponse])
async def get_quiz_resume(
    quiz_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
) -> APIResponse[QuizResponse]:
    """Return an owned quiz session so an unfinished run can be continued."""

    try:
        session = await get_history_service().get_quiz_session(
            current_user.user_id,
            quiz_id,
        )
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="Quiz session retrieved successfully", data=session)


@router.get("/weak-points", response_model=APIResponse[WeakPointSummary])
async def get_weak_points(
    current_user: Annotated[AuthenticatedUser, Depends(get_required_current_user)],
) -> APIResponse[WeakPointSummary]:
    """Aggregate the caller's most frequent weak knowledge points."""

    try:
        summary = await get_weak_point_service().get_weak_points(current_user.user_id)
    except QuizAppException as error:
        _raise_user_error(error)

    return APIResponse(code=0, message="Weak points retrieved successfully", data=summary)
