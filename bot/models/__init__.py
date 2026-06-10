"""Dataclass models mirroring the MongoDB documents used by the bot."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    """A Telegram user known to the bot (``users`` collection)."""

    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    join_date: datetime = field(default_factory=_utcnow)
    processed_files: int = 0
    premium_status: bool = False
    banned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            user_id=data["user_id"],
            username=data.get("username"),
            first_name=data.get("first_name"),
            join_date=data.get("join_date", _utcnow()),
            processed_files=data.get("processed_files", 0),
            premium_status=data.get("premium_status", False),
            banned=data.get("banned", False),
        )


@dataclass
class Settings:
    """Per-user processing preferences (``settings`` collection)."""

    user_id: int
    video_codec: str = "libx264"
    crf: int = 23
    preset: str = "medium"
    output_format: str = "mp4"
    upload_as_document: bool = False
    watermark_position: str = "bottom_right"
    watermark_opacity: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        valid = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in valid})


class TaskStatus(str, Enum):
    """Lifecycle states for a processing task."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A queued/running processing job (``tasks`` collection)."""

    task_id: str
    user_id: int
    tool: str
    status: TaskStatus = TaskStatus.QUEUED
    created_at: datetime = field(default_factory=_utcnow)
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class Stats:
    """Aggregated global statistics (``stats`` collection)."""

    total_users: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    tools_usage: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


__all__ = ["User", "Settings", "Task", "TaskStatus", "Stats"]
