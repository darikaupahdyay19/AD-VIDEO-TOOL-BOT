"""Per-user conversation state for multi-step interactive flows.

Several tools require more than one input (e.g. *Video + Audio* needs the user to
send an audio file after picking the tool, *Watermark* collects a type, then a
file/text, then position and opacity).  :class:`StateStore` keeps a small,
in-memory record of where each user is in such a flow keyed by ``user_id``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class UserState:
    """Transient state describing an in-progress interaction."""

    tool: Optional[str] = None
    # The path of the primary video the user sent.
    video_path: Optional[str] = None
    # Message id of the menu/control message so it can be edited in place.
    menu_message_id: Optional[int] = None
    # What input the bot is currently waiting for, e.g. ``"audio"``,
    # ``"subtitle"``, ``"second_video"``, ``"watermark_image"``,
    # ``"watermark_text"`` or ``"custom_crf"``.
    awaiting: Optional[str] = None
    # Arbitrary collected values (selected codec, resolutions, opacity, ...).
    data: Dict[str, Any] = field(default_factory=dict)


class StateStore:
    """A tiny dictionary-backed store of :class:`UserState` objects."""

    def __init__(self) -> None:
        self._states: Dict[int, UserState] = {}

    def get(self, user_id: int) -> Optional[UserState]:
        return self._states.get(user_id)

    def set(self, user_id: int, state: UserState) -> UserState:
        self._states[user_id] = state
        return state

    def ensure(self, user_id: int) -> UserState:
        """Return the existing state or create a fresh one."""
        if user_id not in self._states:
            self._states[user_id] = UserState()
        return self._states[user_id]

    def clear(self, user_id: int) -> None:
        self._states.pop(user_id, None)


state_store = StateStore()

__all__ = ["UserState", "StateStore", "state_store"]
