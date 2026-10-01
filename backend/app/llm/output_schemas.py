from pydantic import BaseModel, Field
from typing import List, Optional
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


class QuizOption(BaseModel):
    """Option in a structured quiz question"""
    key: str = Field(..., description="Option identifier (A, B, C, D)")
    text: str = Field(..., description="Option text content")


class StructuredQuestion(BaseModel):
    """Structured question from LLM output"""
    id: str = Field(..., description="Question ID like q1, q2, etc.")
    type: QuestionType = Field(..., description="Question type")
    stem: str = Field(..., description="Question text")
    options: List[QuizOption] = Field(..., description="Available options")
    answer: List[str] = Field(..., description="Correct answer keys")
    explanation: str = Field(..., description="Detailed explanation")
    knowledge_point: str = Field(..., description="Related knowledge point")
    difficulty: DifficultyLevel = Field(..., description="Question difficulty")


class StructuredQuizOutput(BaseModel):
    """Structured quiz output from LLM"""
    title: str = Field(..., description="Quiz title")
    summary: str = Field(..., description="Quiz summary/description")
    questions: List[StructuredQuestion] = Field(..., description="List of questions")


class StructuredReportOutput(BaseModel):
    """Structured report output from LLM"""
    accuracy: int = Field(..., ge=0, le=100, description="Accuracy percentage")
    mastered_points: List[str] = Field(..., description="Mastered knowledge points")
    weak_points: List[str] = Field(..., description="Weak knowledge points")
    three_line_summary: List[str] = Field(..., description="Three key takeaways")
    advice: List[str] = Field(..., description="Learning advice")
    share_quote: str = Field(..., description="Quote for sharing")
