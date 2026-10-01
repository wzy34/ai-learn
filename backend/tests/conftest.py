import pytest
import os
from app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables"""
    # Set test environment variables
    os.environ.setdefault("DEEPSEEK_API_KEY", "test_key_for_testing")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing"""
    return {
        "title": "Test Quiz",
        "summary": "A test quiz for unit testing",
        "questions": [
            {
                "id": "q1",
                "type": "single",
                "stem": "What is the capital of France?",
                "options": [
                    {"key": "A", "text": "London"},
                    {"key": "B", "text": "Berlin"},
                    {"key": "C", "text": "Paris"}
                ],
                "answer": ["C"],
                "explanation": "Paris is the capital of France",
                "knowledge_point": "Geography",
                "difficulty": "easy"
            }
        ]
    }
