import uuid
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import InvalidAvatarError

# Images are identified by their real bytes, so a renamed file cannot masquerade
# as an image; the detected signature only decides the saved file extension.
_IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
)

# main.py serves AVATAR_UPLOAD_DIR under this path prefix.
AVATAR_STATIC_PATH = "/static/avatars"


class AvatarStorage:
    """Persist avatar images on disk and expose them as public URLs."""

    def __init__(
        self,
        upload_dir: str | None = None,
        base_url: str | None = None,
        max_size_bytes: int | None = None,
    ) -> None:
        self._upload_dir = Path(upload_dir or settings.AVATAR_UPLOAD_DIR)
        self._base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self._max_size_bytes = (
            max_size_bytes
            if max_size_bytes is not None
            else settings.AVATAR_MAX_SIZE_MB * 1024 * 1024
        )

    def save(self, user_id: int, content: bytes) -> str:
        """Validate an avatar image, store it, and return its public URL."""
        extension = self._detect_extension(content)

        directory = self._upload_dir / str(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.{extension}"
        (directory / filename).write_bytes(content)

        return f"{self._base_url}{AVATAR_STATIC_PATH}/{user_id}/{filename}"

    def delete(self, avatar_url: str) -> None:
        """Best-effort removal of a file previously returned by save()."""
        prefix = f"{AVATAR_STATIC_PATH}/"
        relative = avatar_url.split(prefix, 1)[-1]
        if relative == avatar_url:
            # The URL was not produced by this storage; never delete it.
            return

        target = (self._upload_dir / relative).resolve()
        if self._upload_dir.resolve() not in target.parents:
            return
        target.unlink(missing_ok=True)

    def _detect_extension(self, content: bytes) -> str:
        if not content:
            raise InvalidAvatarError(detail="Avatar file is empty")
        if len(content) > self._max_size_bytes:
            max_mb = self._max_size_bytes // (1024 * 1024)
            raise InvalidAvatarError(
                detail=f"Avatar must be smaller than {max_mb} MB"
            )

        for signature, extension in _IMAGE_SIGNATURES:
            if content.startswith(signature):
                return extension
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "webp"

        raise InvalidAvatarError()


_avatar_storage: AvatarStorage | None = None


def get_avatar_storage() -> AvatarStorage:
    """Get the shared avatar storage."""

    global _avatar_storage
    if _avatar_storage is None:
        _avatar_storage = AvatarStorage()
    return _avatar_storage
