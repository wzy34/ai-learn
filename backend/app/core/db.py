from asyncio import Lock
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiomysql

from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger

logger = get_logger(__name__)


class Database:
    """Lazily initialized MySQL pool shared by user-system repositories."""

    def __init__(self) -> None:
        self._pool: aiomysql.Pool | None = None
        self._connect_lock = Lock()

    async def connect(self) -> None:
        """Create the pool only once, when a user data operation needs it."""

        if self._pool is not None:
            return

        # Concurrent first requests must not each create their own pool.
        async with self._connect_lock:
            if self._pool is not None:
                return

            try:
                self._pool = await aiomysql.create_pool(
                    host=settings.MYSQL_HOST,
                    port=settings.MYSQL_PORT,
                    user=settings.MYSQL_USER,
                    password=settings.MYSQL_PASSWORD,
                    db=settings.MYSQL_DATABASE,
                    minsize=settings.MYSQL_POOL_MIN_SIZE,
                    maxsize=settings.MYSQL_POOL_MAX_SIZE,
                    connect_timeout=settings.MYSQL_CONNECT_TIMEOUT,
                    charset="utf8mb4",
                    autocommit=False,
                    pool_recycle=3600,
                )
            except (aiomysql.Error, OSError, TimeoutError) as error:
                logger.error(
                    "Failed to create MySQL pool",
                    host=settings.MYSQL_HOST,
                    database=settings.MYSQL_DATABASE,
                    error=str(error),
                )
                raise DatabaseError(
                    "Unable to connect to the user data store"
                ) from error

    async def close(self) -> None:
        """Close a previously initialized pool during application shutdown."""

        if self._pool is None:
            return

        self._pool.close()
        await self._pool.wait_closed()
        self._pool = None

    async def _get_pool(self) -> aiomysql.Pool:
        await self.connect()
        if self._pool is None:
            raise DatabaseError("MySQL pool is unavailable")
        return self._pool

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiomysql.Connection, None]:
        """Acquire and release a single connection from the shared pool."""

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiomysql.Connection, None]:
        """Commit successful work and roll back any failed repository action."""

        async with self.connection() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise
            else:
                await connection.commit()


database = Database()
