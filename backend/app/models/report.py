from pydantic import BaseModel, Field
from typing import List, Optional
from app.models.quiz import Question


class AnswerRecord(BaseModel):
    """Single answer record"""
    question_id: str = Field(..., description="Question identifier")
    selected_answers: List[str] = Field(..., description="User's selected answers")
    is_correct: bool = Field(..., description="Whether the answer is correct")
    duration_ms: int = Field(..., ge=0, description="Time taken to answer in milliseconds")


class Report(BaseModel):
    """Learning report data"""
    accuracy: int = Field(..., ge=0, le=100, description="Accuracy percentage")
    mastered_points: List[str] = Field(..., description="Mastered knowledge points")
    weak_points: List[str] = Field(..., description="Weak knowledge points")
    three_line_summary: List[str] = Field(..., description="Three key takeaways")
    advice: List[str] = Field(..., description="Learning advice")
    share_quote: str = Field(..., description="Quote for sharing")


class ReportCreateRequest(BaseModel):
    """Request model for report generation"""
    quiz_id: str = Field(..., description="Quiz identifier")
    topic: str = Field(..., description="Learning topic")
    questions: List[Question] = Field(..., description="Quiz questions")
    answer_records: List[AnswerRecord] = Field(..., description="User's answer records")


class ReportResponse(BaseModel):
    """Response model for report generation"""
    accuracy: int
    mastered_points: List[str]
    weak_points: List[str]
    three_line_summary: List[str]
    advice: List[str]
    share_quote: str
