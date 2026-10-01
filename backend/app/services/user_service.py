from app.clients.wechat_client import WechatClient, get_wechat_client
from app.core.auth import create_access_token
from app.models.user import LoginResponse, UpdateProfileRequest, UserProfile, UserSummary
from app.repositories.user_repository import (
    StoredProfile,
    UserRepository,
    get_user_repository,
)
from app.services.avatar_storage import AvatarStorage, get_avatar_storage


class UserService:
    """Application service for login and profile operations."""

    def __init__(
        self,
        user_repository: UserRepository | None = None,
        wechat_client: WechatClient | None = None,
        avatar_storage: AvatarStorage | None = None,
    ) -> None:
        self._user_repository = user_repository or get_user_repository()
        self._wechat_client = wechat_client or get_wechat_client()
        self._avatar_storage = avatar_storage or get_avatar_storage()

    async def login_with_code(self, code: str) -> LoginResponse:
        session = await self._wechat_client.exchange_code(code)
        user = await self._user_repository.get_or_create_by_openid(session.openid)
        return LoginResponse(
            token=create_access_token(user_id=user.id, openid=user.openid),
            user=UserSummary(
                id=user.id,
                nickname=user.nickname,
                avatar_url=user.avatar_url,
                total_xp=user.total_xp,
            ),
        )

    async def get_profile(self, user_id: int) -> UserProfile:
        profile = await self._user_repository.get_profile(user_id)
        return self._build_profile(profile)

    async def update_profile(
        self,
        user_id: int,
        request: UpdateProfileRequest,
    ) -> UserProfile:
        profile = await self._user_repository.update_profile(user_id, request)
        return self._build_profile(profile)

    async def update_avatar(self, user_id: int, content: bytes) -> UserProfile:
        """Store an uploaded image and make it the caller's avatar."""
        avatar_url = self._avatar_storage.save(user_id, content)
        try:
            previous = await self._user_repository.get_profile(user_id)
            profile = await self._user_repository.update_profile(
                user_id,
                UpdateProfileRequest(avatar_url=avatar_url),
            )
        except Exception:
            # The stored image is useless without its database row.
            self._avatar_storage.delete(avatar_url)
            raise

        if previous.avatar_url != avatar_url:
            self._avatar_storage.delete(previous.avatar_url)
        return self._build_profile(profile)

    @staticmethod
    def _build_profile(profile: StoredProfile) -> UserProfile:
        return UserProfile(
            id=profile.id,
            nickname=profile.nickname,
            avatar_url=profile.avatar_url,
            total_xp=profile.total_xp,
            quiz_count=profile.quiz_count,
            correct_count=profile.correct_count,
            average_accuracy=profile.average_accuracy,
        )


_user_service: UserService | None = None


def get_user_service() -> UserService:
    """Get the shared user service."""

    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
