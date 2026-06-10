"""Asynchronous MongoDB data-access layer built on Motor.

The :class:`Database` class wraps the four collections used by the bot
(``users``, ``settings``, ``tasks`` and ``stats``) and exposes high level
coroutines.  A single shared instance is created as :data:`db` at import time;
call :meth:`Database.connect` during start-up before issuing queries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from bot.config import Config
from bot.models import Settings, Stats, Task, User
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class Database:
    """Thin async wrapper around the bot's MongoDB collections."""

    def __init__(self, uri: str, db_name: str) -> None:
        self._uri = uri
        self._db_name = db_name
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None

    # ------------------------------------------------------------------ setup
    async def connect(self) -> None:
        """Open the connection and ensure indexes exist."""
        self._client = AsyncIOMotorClient(self._uri, serverSelectionTimeoutMS=8000)
        self._db = self._client[self._db_name]
        # Fail fast if the server is unreachable.
        await self._client.admin.command("ping")
        await self._ensure_indexes()
        logger.info("Connected to MongoDB database '%s'", self._db_name)

    async def close(self) -> None:
        """Close the underlying client."""
        if self._client is not None:
            self._client.close()
            logger.info("Closed MongoDB connection")

    async def _ensure_indexes(self) -> None:
        assert self._db is not None
        await self._db.users.create_index("user_id", unique=True)
        await self._db.settings.create_index("user_id", unique=True)
        await self._db.tasks.create_index("task_id", unique=True)
        await self._db.tasks.create_index("user_id")

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            raise RuntimeError("Database.connect() must be called before use")
        return self._db

    # ------------------------------------------------------------------ users
    async def add_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> User:
        """Insert the user if new and return the stored :class:`User`."""
        existing = await self.db.users.find_one({"user_id": user_id})
        if existing:
            return User.from_dict(existing)
        user = User(user_id=user_id, username=username, first_name=first_name)
        await self.db.users.insert_one(user.to_dict())
        logger.debug("Registered new user %s", user_id)
        return user

    async def get_user(self, user_id: int) -> Optional[User]:
        doc = await self.db.users.find_one({"user_id": user_id})
        return User.from_dict(doc) if doc else None

    async def is_banned(self, user_id: int) -> bool:
        doc = await self.db.users.find_one({"user_id": user_id}, {"banned": 1})
        return bool(doc and doc.get("banned"))

    async def set_banned(self, user_id: int, banned: bool) -> None:
        await self.db.users.update_one(
            {"user_id": user_id}, {"$set": {"banned": banned}}, upsert=True
        )

    async def set_premium(self, user_id: int, premium: bool) -> None:
        await self.db.users.update_one(
            {"user_id": user_id}, {"$set": {"premium_status": premium}}, upsert=True
        )

    async def increment_processed(self, user_id: int, amount: int = 1) -> None:
        await self.db.users.update_one(
            {"user_id": user_id}, {"$inc": {"processed_files": amount}}
        )

    async def total_users(self) -> int:
        return await self.db.users.count_documents({})

    async def all_user_ids(self) -> List[int]:
        return [doc["user_id"] async for doc in self.db.users.find({}, {"user_id": 1})]

    # --------------------------------------------------------------- settings
    async def get_settings(self, user_id: int) -> Settings:
        doc = await self.db.settings.find_one({"user_id": user_id})
        if doc:
            return Settings.from_dict(doc)
        settings = Settings(user_id=user_id)
        await self.db.settings.insert_one(settings.to_dict())
        return settings

    async def update_settings(self, user_id: int, **fields: Any) -> None:
        if not fields:
            return
        await self.db.settings.update_one(
            {"user_id": user_id}, {"$set": fields}, upsert=True
        )

    # ------------------------------------------------------------------ tasks
    async def save_task(self, task: Task) -> None:
        await self.db.tasks.update_one(
            {"task_id": task.task_id}, {"$set": task.to_dict()}, upsert=True
        )

    async def update_task_status(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> None:
        update: Dict[str, Any] = {"status": status}
        if status in {"completed", "failed", "cancelled"}:
            update["finished_at"] = datetime.now(timezone.utc)
        if error is not None:
            update["error"] = error
        await self.db.tasks.update_one({"task_id": task_id}, {"$set": update})

    # ------------------------------------------------------------------ stats
    async def record_tool_usage(self, tool: str) -> None:
        await self.db.stats.update_one(
            {"_id": "global"},
            {"$inc": {f"tools_usage.{tool}": 1, "total_tasks": 1}},
            upsert=True,
        )

    async def record_task_result(self, completed: bool) -> None:
        key = "completed_tasks" if completed else "failed_tasks"
        await self.db.stats.update_one(
            {"_id": "global"}, {"$inc": {key: 1}}, upsert=True
        )

    async def get_stats(self) -> Stats:
        doc = await self.db.stats.find_one({"_id": "global"}) or {}
        stats = Stats(
            total_users=await self.total_users(),
            total_tasks=doc.get("total_tasks", 0),
            completed_tasks=doc.get("completed_tasks", 0),
            failed_tasks=doc.get("failed_tasks", 0),
            tools_usage=doc.get("tools_usage", {}),
        )
        return stats


# Shared instance used across the application.
db = Database(Config.MONGO_URI, Config.MONGO_DB_NAME)

__all__ = ["Database", "db"]
