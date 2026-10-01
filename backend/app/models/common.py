from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, Any

T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    """Standard API response format"""
    code: int = Field(0, description="Response code, 0 for success")
    message: str = Field("ok", description="Response message")
    data: Optional[T] = Field(None, description="Response data")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field("ok", description="Service status")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Running environment")


class ErrorResponse(BaseModel):
    """Error response format"""
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Any] = Field(None, description="Additional error data")
