from typing import Any, Optional
from fastapi import HTTPException, status


class QuizAppException(HTTPException):
    """Base exception for quiz application errors"""

    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Optional[dict] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class QuizGenerationError(QuizAppException):
    """Exception raised when quiz generation fails"""

    def __init__(
        self,
        detail: str = "Failed to generate quiz",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class QuizValidationError(QuizAppException):
    """Exception raised when quiz validation fails"""

    def __init__(
        self,
        detail: str = "Quiz validation failed",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class LLMError(QuizAppException):
    """Exception raised when LLM call fails"""

    def __init__(
        self,
        detail: str = "LLM call failed",
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class SearchNoResultsError(QuizAppException):
    """Exception raised when retrieval ran but yielded no usable material.

    This is deliberately distinct from a search-service failure (which
    degrades to pure-model generation): a topic that cannot be found on
    the web at all must not silently produce possibly-off-topic questions.
    """

    def __init__(
        self,
        detail: str = "未能在网络检索到该主题的资料，请换个说法或补充更多背景信息后再试",
        status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class ReportGenerationError(QuizAppException):
    """Exception raised when report generation fails"""

    def __init__(
        self,
        detail: str = "Failed to generate report",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class ReportValidationError(QuizAppException):
    """Exception raised when report validation fails"""

    def __init__(
        self,
        detail: str = "Report validation failed",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class InvalidAvatarError(QuizAppException):
    """Exception raised when an uploaded avatar file is not acceptable."""

    def __init__(
        self,
        detail: str = "Avatar must be a JPG, PNG, or WebP image",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class AuthenticationError(QuizAppException):
    """Exception raised when authentication cannot be completed."""

    def __init__(
        self,
        detail: str = "Authentication token is invalid or expired",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class WechatLoginError(QuizAppException):
    """Exception raised when WeChat cannot exchange a login code."""

    def __init__(
        self,
        detail: str = "WeChat login failed",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class DatabaseError(QuizAppException):
    """Exception raised when user data cannot be stored or read."""

    def __init__(
        self,
        detail: str = "Database operation failed",
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class UserNotFoundError(QuizAppException):
    """Exception raised when a user does not exist."""

    def __init__(
        self,
        detail: str = "User not found",
        status_code: int = status.HTTP_404_NOT_FOUND,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


class HistoryNotFoundError(QuizAppException):
    """Exception raised when a user cannot access a learning history entry."""

    def __init__(
        self,
        detail: str = "Learning history not found",
        status_code: int = status.HTTP_404_NOT_FOUND,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
