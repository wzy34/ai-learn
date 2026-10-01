from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import aiomysql

from app.core.db import Database, database
from app.core.exceptions import DatabaseError, UserNotFoundError
from app.models.user import UpdateProfileRequest


@dataclass(frozen=True)
class StoredUser:
    id: int
    openid: str
    nickname: str
    avatar_url: str
    total_xp: int


@dataclass(frozen=True)
class StoredProfile(StoredUser):
    quiz_count: int
    correct_count: int
    average_accuracy: float


class UserRepository:
    """Parameterised MySQL access for users and their aggregate statistics."""

    def __init__(self, db: Database = database) -> None:
        self._db = db

    async def get_or_create_by_openid(self, openid: str) -> StoredUser:
        async with self._db.transaction() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO users (openid)
                    VALUES (%s)
                    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
                    """,
                    (openid,),
                )
                await cursor.execute(
                    """
                    SELECT id, openid, nickname, avatar_url, total_xp
                    FROM users
                    WHERE openid = %s
                    """,
                    (openid,),
                )
                row = await cursor.fetchone()

        if row is None:
            raise DatabaseError("Unable to load the signed-in user")
        return self._to_stored_user(row)

    async def get_profile(self, user_id: int) -> StoredProfile:
        async with self._db.connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT
                        u.id,
                        u.openid,
                        u.nickname,
                        u.avatar_url,
                        u.total_xp,
                        COUNT(ar.id) AS quiz_count,
                        COALESCE(SUM(ar.correct_count), 0) AS correct_count,
                        COALESCE(ROUND(AVG(ar.accuracy), 2), 0) AS average_accuracy
                    FROM users AS u
                    LEFT JOIN answer_records AS ar ON ar.user_id = u.id
                    WHERE u.id = %s
                    GROUP BY u.id, u.openid, u.nickname, u.avatar_url, u.total_xp
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()

        if row is None:
            raise UserNotFoundError()
        return StoredProfile(
            **self._to_stored_user(row).__dict__,
            quiz_count=int(row["quiz_count"]),
            correct_count=int(row["correct_count"]),
            average_accuracy=self._to_float(row["average_accuracy"]),
        )

    async def update_profile(
        self,
        user_id: int,
        request: UpdateProfileRequest,
    ) -> StoredProfile:
        assignments: list[str] = []
        parameters: list[Any] = []
        if request.nickname is not None:
            assignments.append("nickname = %s")
            parameters.append(request.nickname)
        if request.avatar_url is not None:
            assignments.append("avatar_url = %s")
            parameters.append(request.avatar_url)

        if not assignments:
            raise DatabaseError("No profile fields were provided")

        parameters.append(user_id)
        async with self._db.transaction() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    f"UPDATE users SET {', '.join(assignments)} WHERE id = %s",
                    tuple(parameters),
                )
                # MySQL reports only *changed* rows here, so re-saving the same
                # nickname yields 0; existence is verified by the read below.

        return await self.get_profile(user_id)

    @staticmethod
    def _to_stored_user(row: dict[str, Any]) -> StoredUser:
        return StoredUser(
            id=int(row["id"]),
            openid=str(row["openid"]),
            nickname=str(row["nickname"]),
            avatar_url=str(row["avatar_url"]),
            total_xp=int(row["total_xp"]),
        )

    @staticmethod
    def _to_float(value: Decimal | float | int) -> float:
        return float(value)


_user_repository: UserRepository | None = None


def get_user_repository() -> UserRepository:
    """Get the shared user repository."""

    global _user_repository
    if _user_repository is None:
        _user_repository = UserRepository()
    return _user_repository
