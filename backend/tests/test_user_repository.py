"""Regression tests for profile updates under MySQL changed-row semantics."""

from contextlib import asynccontextmanager

import pytest

from app.core.exceptions import UserNotFoundError
from app.models.user import UpdateProfileRequest
from app.repositories.user_repository import UserRepository


class FakeCursor:
    """Cursor stand-in that reproduces MySQL's UPDATE row-count behaviour."""

    def __init__(self, db_state):
        self._db_state = db_state
        self._row = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, query, params=None):
        normalized = " ".join(query.split())
        if normalized.startswith("UPDATE users"):
            nickname = params[0]
            user = self._db_state["users"].get(self._db_state["user_id"])
            if user is not None and user["nickname"] == nickname:
                # MySQL counts changed rows, so a no-op update reports 0.
                self._db_state["last_rowcount"] = 0
            else:
                if user is not None:
                    user["nickname"] = nickname
                self._db_state["last_rowcount"] = 1
        elif normalized.startswith("SELECT"):
            user = self._db_state["users"].get(self._db_state["user_id"])
            self._row = (
                None
                if user is None
                else {
                    **user,
                    "quiz_count": 0,
                    "correct_count": 0,
                    "average_accuracy": 0,
                }
            )
        else:  # pragma: no cover - guards against unexpected statements
            raise AssertionError(f"Unexpected query: {normalized}")

    async def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, db_state):
        self._db_state = db_state

    def cursor(self, cursor_class=None):
        return FakeCursor(self._db_state)

    async def commit(self):
        pass

    async def rollback(self):
        pass


class FakeDatabase:
    def __init__(self, db_state):
        self._db_state = db_state

    @asynccontextmanager
    async def connection(self):
        yield FakeConnection(self._db_state)

    @asynccontextmanager
    async def transaction(self):
        connection = FakeConnection(self._db_state)
        try:
            yield connection
        except Exception:
            await connection.rollback()
            raise
        else:
            await connection.commit()


def build_state(user_id=54, nickname="学习者"):
    return {
        "user_id": user_id,
        "users": {
            user_id: {
                "id": user_id,
                "openid": "wx-openid-1",
                "nickname": nickname,
                "avatar_url": "",
                "total_xp": 0,
            }
        },
    }


@pytest.mark.asyncio
async def test_resaving_an_unchanged_nickname_succeeds():
    """A same-value update changes 0 rows but must not be treated as missing."""

    repository = UserRepository(FakeDatabase(build_state()))

    profile = await repository.update_profile(
        54, UpdateProfileRequest(nickname="学习者")
    )

    assert profile.nickname == "学习者"


@pytest.mark.asyncio
async def test_updating_a_missing_user_still_raises_user_not_found():
    state = build_state()
    state["user_id"] = 999  # token points at a user that no longer exists
    repository = UserRepository(FakeDatabase(state))

    with pytest.raises(UserNotFoundError):
        await repository.update_profile(
            999, UpdateProfileRequest(nickname="新昵称")
        )
