import re
from typing import str


def clean_user_input(text: str) -> str:
    """Clean and normalize user input text

    Args:
        text: Raw user input

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    # Remove special characters that might cause issues
    # Keep alphanumeric, Chinese characters, and common punctuation
    text = re.sub(r'[^\w\s一-鿿,。!?;:、，！？；：""''\-\(\)\[\]]', '', text)

    return text


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix
