"""Incoming media handling: show the tool menu and collect extra inputs."""

from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from bot.config import Config
from bot.database import db
from bot.handlers.tools import run_tool
from bot.helpers.files import within_size_limit
from bot.helpers.formatting import human_bytes
from bot.keyboards import (
    language_keyboard,
    video_tools_keyboard,
    watermark_position_keyboard,
)
from bot.plugins.guards import passes_guards
from bot.utils.logger import get_logger
from bot.utils.state import state_store

logger = get_logger(__name__)

# Media that can start a flow or satisfy a pending request.
_MEDIA = filters.video | filters.document | filters.audio | filters.photo | filters.animation


def _is_video(message: Message) -> bool:
    if message.video or message.animation:
        return True
    doc = message.document
    return bool(doc and (doc.mime_type or "").startswith("video"))


def _media_size(message: Message) -> int:
    media = message.video or message.document or message.audio or message.animation
    return getattr(media, "file_size", 0) or 0


@Client.on_message(_MEDIA & filters.private)
async def media_handler(client: Client, message: Message) -> None:
    if not await passes_guards(message):
        return

    user_id = message.from_user.id
    state = state_store.get(user_id)

    # If we are waiting for an additional input, route the media there.
    if state and state.awaiting in {"second_video", "audio", "subtitle", "watermark_image"}:
        await _collect_input(client, message, state)
        return

    # Otherwise this must be a fresh source video.
    if not _is_video(message):
        await message.reply_text("📹 Please send a **video** to get started.")
        return

    size = _media_size(message)
    if size and not within_size_limit(size):
        await message.reply_text(
            f"⚠️ That file is `{human_bytes(size)}`, which exceeds the limit of "
            f"`{human_bytes(Config.MAX_FILE_SIZE)}`."
        )
        return

    await db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    new_state = state_store.ensure(user_id)
    new_state.tool = None
    new_state.awaiting = None
    new_state.data = {"video_msg": message}
    await message.reply_text(
        "🎬 **Choose a tool** for your video:",
        reply_markup=video_tools_keyboard(),
    )


async def _collect_input(client: Client, message: Message, state) -> None:
    """Store a secondary input and either advance the flow or run the tool."""
    user_id = message.from_user.id
    awaiting = state.awaiting

    if awaiting == "second_video":
        if not _is_video(message):
            await message.reply_text("Please send a **video** file.")
            return
        state.data["video2_msg"] = message
    elif awaiting == "audio":
        state.data["audio_msg"] = message
        if state.tool in {"vid_aud", "vid_aud_sub"}:
            # Let the user tag the muxed audio stream with a language.
            state.awaiting = None
            await message.reply_text(
                "🌐 Select the **audio** track language:",
                reply_markup=language_keyboard("lang_a"),
            )
            return
    elif awaiting == "subtitle":
        state.data["sub_msg"] = message
        if state.tool in {"vid_sub", "vid_aud_sub"}:
            state.awaiting = None
            await message.reply_text(
                "🌐 Select the **subtitle** track language:",
                reply_markup=language_keyboard("lang_s"),
            )
            return
    elif awaiting == "watermark_image":
        state.data["wm_msg"] = message
        state.awaiting = None
        await message.reply_text(
            "📍 Choose the watermark **position**:",
            reply_markup=watermark_position_keyboard(),
        )
        return

    state.awaiting = None
    status = await message.reply_text("✅ Received. Preparing…")
    await run_tool(client, message.chat.id, user_id, status, state)


@Client.on_message(filters.text & filters.private & ~filters.command(
    ["start", "help", "about", "settings", "ping", "stats",
     "broadcast", "users", "ban", "unban", "logs", "restart"]
))
async def text_input_handler(client: Client, message: Message) -> None:
    """Capture free-text input for custom CRF and text watermarks."""
    user_id = message.from_user.id
    state = state_store.get(user_id)
    if not state or state.awaiting not in {"custom_crf", "watermark_text"}:
        return
    if not await passes_guards(message):
        return

    if state.awaiting == "custom_crf":
        try:
            crf = int(message.text.strip())
        except ValueError:
            await message.reply_text("Please send a number between 0 and 51.")
            return
        state.data["crf"] = max(0, min(51, crf))
        state.awaiting = None
        status = await message.reply_text("✅ CRF set. Preparing…")
        await run_tool(client, message.chat.id, user_id, status, state)
    elif state.awaiting == "watermark_text":
        state.data["text"] = message.text.strip()[:200]
        state.awaiting = None
        await message.reply_text(
            "📍 Choose the watermark **position**:",
            reply_markup=watermark_position_keyboard(),
        )
