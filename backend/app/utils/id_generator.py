import uuid


def generate_quiz_id() -> str:
    """Generate a unique quiz ID

    Returns:
        Unique quiz ID
    """
    return f"quiz_{uuid.uuid4().hex[:12]}"


def generate_question_id(index: int) -> str:
    """Generate a question ID

    Args:
        index: Question index (0-based)

    Returns:
        Question ID like q1, q2, etc.
    """
    return f"q{index + 1}"
