from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum


class DifficultyLevel(str, Enum):
    """Question difficulty levels"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    """Question types"""
    SINGLE = "single"
    MULTIPLE = "multiple"
    JUDGE = "judge"


class Option(BaseModel):
    """Question option"""
    key: str = Field(..., description="Option identifier (A, B, C, D)")
    text: str = Field(..., description="Option text content")


class Question(BaseModel):
    """Single question in a quiz"""
    id: str = Field(..., description="Unique question identifier")
    type: QuestionType = Field(..., description="Question type")
    stem: str = Field(..., description="Question stem/prompt")
    options: List[Option] = Field(..., description="Available options")
    answer: List[str] = Field(..., description="Correct answer keys")
    explanation: str = Field(..., description="Detailed explanation")
    knowledge_point: str = Field(..., description="Related knowledge point")
    difficulty: DifficultyLevel = Field(..., description="Question difficulty")

    class Config:
        use_enum_values = True


class Quiz(BaseModel):
    """Complete quiz data"""
    quiz_id: str = Field(..., description="Unique quiz identifier")
    title: str = Field(..., description="Quiz title")
    summary: str = Field(..., description="Quiz description/summary")
    source_type: str = Field(default="text", description="Input source type")
    user_input: str = Field(..., description="Original user input")
    questions: List[Question] = Field(..., description="List of questions")


class QuizCreateRequest(BaseModel):
    """Request model for quiz generation"""
    user_input: str = Field(..., min_length=1, max_length=5000, description="User's learning content")
    question_count: Optional[int] = Field(default=5, ge=1, le=10, description="Number of questions to generate")
    difficulty: Optional[Literal["easy", "medium", "hard", "mixed"]] = Field(
        default="mixed", description="Question difficulty level"
    )


class SearchSource(BaseModel):
    """A web source used to ground quiz generation"""
    title: str = Field(..., description="Source page title (URL as fallback)")
    url: str = Field(..., description="Source URL")


class QuizResponse(BaseModel):
    """Response model for quiz generation"""
    quiz_id: str
    title: str
    summary: str
    questions: List[Question]
    # Generation-time retrieval metadata; not persisted with history.
    search_used: bool = Field(default=False, description="Whether web material grounded this quiz")
    sources: List[SearchSource] = Field(default_factory=list, description="Web sources used")


class DrillCreateRequest(BaseModel):
    """Request model for weak-point drill generation

    When `focus` is omitted the backend picks the user's most frequent
    weak knowledge point from their recent reports.
    """
    focus: Optional[str] = Field(default=None, min_length=1, max_length=100, description="Weak knowledge point to drill")
    question_count: Optional[int] = Field(default=5, ge=1, le=10, description="Number of questions to generate")
