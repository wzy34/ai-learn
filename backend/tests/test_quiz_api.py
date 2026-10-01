import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import AsyncMock, patch
from app.models.quiz import QuizResponse, Question, Option, QuestionType, DifficultyLevel


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def mock_quiz_response():
    """Mock quiz response data"""
    return QuizResponse(
        quiz_id="test_quiz_123",
        title="Test Quiz",
        summary="A test quiz",
        questions=[
            Question(
                id="q1",
                type=QuestionType.SINGLE,
                stem="What is 2+2?",
                options=[
                    Option(key="A", text="3"),
                    Option(key="B", text="4"),
                    Option(key="C", text="5")
                ],
                answer=["B"],
                explanation="2+2=4",
                knowledge_point="Basic arithmetic",
                difficulty=DifficultyLevel.EASY
            )
        ]
    )


class TestQuizAPI:
    """Tests for quiz generation API"""

    @pytest.mark.asyncio
    async def test_generate_quiz_success(self, client, mock_quiz_response):
        """Test successful quiz generation (with mocked LLM)"""

        # Mock the quiz service
        mock_service = AsyncMock()
        mock_service.generate_quiz = AsyncMock(return_value=mock_quiz_response)

        with patch('app.api.v1.routes.quiz.get_quiz_service', return_value=mock_service):
            # Make request
            response = client.post(
                "/api/v1/quiz/generate",
                json={
                    "user_input": "I want to learn about basic math",
                    "question_count": 1,
                    "difficulty": "easy"
                }
            )

            # Assert response
            assert response.status_code == 200
            data = response.json()

            assert data["code"] == 0
            assert data["message"] == "Quiz generated successfully"
            assert "data" in data
            assert data["data"]["quiz_id"] == "test_quiz_123"
            assert len(data["data"]["questions"]) == 1

    def test_generate_quiz_empty_input(self, client):
        """Test quiz generation with empty input"""
        response = client.post(
            "/api/v1/quiz/generate",
            json={
                "user_input": "",
                "question_count": 5
            }
        )

        # Should fail validation
        assert response.status_code == 422

    def test_generate_quiz_too_long_input(self, client):
        """Test quiz generation with input exceeding max length"""
        response = client.post(
            "/api/v1/quiz/generate",
            json={
                "user_input": "a" * 6000,  # Exceeds 5000 character limit
                "question_count": 5
            }
        )

        # Should fail with validation error from service
        assert response.status_code in [400, 422]

    def test_generate_quiz_invalid_question_count(self, client):
        """Test quiz generation with invalid question count"""
        response = client.post(
            "/api/v1/quiz/generate",
            json={
                "user_input": "Test content",
                "question_count": 15  # Exceeds max of 10
            }
        )

        assert response.status_code == 422
