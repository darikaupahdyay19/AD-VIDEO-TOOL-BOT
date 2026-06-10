"""Central callback-query dispatcher for every inline button in the bot."""

from __future__ import annotations

from pyrogram import Client
from pyrogram.types import CallbackQuery

from bot.database import db
from bot.handlers.tools import run_tool
from bot.keyboards import (
    convert_format_keyboard,
    encode_codec_keyboard,
    encode_quality_keyboard,
    extract_audio_keyboard,
    extract_subs_keyboard,
    multires_keyboard,
    remove_streams_keyboard,
    settings_keyboard,
    video_tools_keyboard,
    watermark_opacity_keyboard,
    watermark_type_keyboard,
)
from bot.plugins.guards import passes_guards
from bot.utils.logger import get_logger
from bot.utils.queue import queue
from bot.utils.state import state_store

logger = get_logger(__name__)

# Tools that need an extra uploaded file before they can run.
_AWAIT_PROMPTS = {
    "vid_vid": ("second_video", "➕ Send the **second video** to merge."),
    "vid_aud": ("audio", "🎵 Send the **audio** file to set as the new track."),
    "vid_sub": ("subtitle", "💬 Send the **subtitle** file (SRT/ASS/VTT)."),
    "vid_aud_sub": ("audio", "🎵 Send the **audio** file (subtitle next)."),
    "hardsub": ("subtitle", "🔥 Send the **subtitle** file to burn in."),
    "swap_audio": ("audio", "🔀 Send the **audio** file to swap in."),
}

# Tools that run immediately once selected (only need the source video).
_IMMEDIATE = {"introsub", "rm_subs", "rm_audio", "strip_meta"}

# Setting cycles for the /settings menu.
_SETTING_CYCLES = {
    "codec": ("video_codec", ["libx264", "libx265", "libaom-av1", "libvpx-vp9"]),
    "preset": ("preset", ["ultrafast", "veryfast", "fast", "medium", "slow"]),
    "crf": ("crf", [18, 20, 23, 26, 28]),
    "format": ("output_format", ["mp4", "mkv", "webm", "mov"]),
}


@Client.on_callback_query()
async def on_callback(client: Client, query: CallbackQuery) -> None:
    if not await passes_guards(query):
        return

    data = query.data or ""
    parts = data.split("|")
    namespace = parts[0]
    handler = _ROUTES.get(namespace)
    if handler is None:
        await query.answer()
        return
    try:
        await handler(client, query, parts)
    except Exception as exc:  # keep the bot responsive on unexpected errors
        logger.exception("Callback %s failed: %s", data, exc)
        await query.answer("Something went wrong. Please resend your video.", show_alert=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _require_state(query: CallbackQuery):
    """Return the user's state or ``None`` (answering the query if missing)."""
    state = state_store.get(query.from_user.id)
    if not state or "video_msg" not in state.data:
        return None
    return state


async def _start_processing(client: Client, query: CallbackQuery, state) -> None:
    await query.message.edit_text("⏳ Added to queue…")
    await run_tool(
        client, query.message.chat.id, query.from_user.id, query.message, state
    )


# --------------------------------------------------------------------------- #
# Route handlers
# --------------------------------------------------------------------------- #

async def _menu(client, query, parts) -> None:
    action = parts[1]
    if action == "main":
        state = _require_state(query)
        if state is None:
            await query.answer("Session expired — resend your video.", show_alert=True)
            return
        state.tool = None
        state.awaiting = None
        await query.message.edit_text(
            "🎬 **Choose a tool** for your video:",
            reply_markup=video_tools_keyboard(),
        )
    elif action in {"cancel", "close"}:
        state_store.clear(query.from_user.id)
        await query.message.edit_text("❌ Cancelled." if action == "cancel" else "✅ Done.")
    await query.answer()


async def _tool(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired — resend your video.", show_alert=True)
        return
    tool = parts[1]
    state.tool = tool
    state.data.pop("resolutions", None)
    state.data.pop("stream_types", None)

    if tool == "encode":
        await query.message.edit_text(
            "🎞 Choose a **codec**:", reply_markup=encode_codec_keyboard()
        )
    elif tool == "convert":
        await query.message.edit_text(
            "🔄 Choose a **format**:", reply_markup=convert_format_keyboard()
        )
    elif tool == "multires":
        state.data["resolutions"] = []
        await query.message.edit_text(
            "📐 Select **resolutions**:", reply_markup=multires_keyboard([])
        )
    elif tool == "rm_streams":
        state.data["stream_types"] = []
        await query.message.edit_text(
            "✂️ Select **streams to remove**:", reply_markup=remove_streams_keyboard([])
        )
    elif tool == "ex_subs":
        await query.message.edit_text(
            "📤 Subtitle **format**:", reply_markup=extract_subs_keyboard()
        )
    elif tool == "ex_audio":
        await query.message.edit_text(
            "🎧 Audio **format**:", reply_markup=extract_audio_keyboard()
        )
    elif tool == "watermark":
        await query.message.edit_text(
            "💧 Watermark **type**:", reply_markup=watermark_type_keyboard()
        )
    elif tool in _AWAIT_PROMPTS:
        awaiting, prompt = _AWAIT_PROMPTS[tool]
        state.awaiting = awaiting
        await query.message.edit_text(prompt)
    elif tool in _IMMEDIATE:
        await _start_processing(client, query, state)
    else:
        await query.answer("Unknown tool.", show_alert=True)
        return
    await query.answer()


async def _enc_codec(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    codec = parts[1]
    state.data["codec"] = codec
    await query.message.edit_text(
        f"🎚 Codec `{codec}` — choose **quality**:",
        reply_markup=encode_quality_keyboard(codec),
    )
    await query.answer()


async def _enc_quality(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    # parts == ["enc_q", codec, quality]
    state.data["codec"] = parts[1]
    quality = parts[2]
    state.data["quality"] = quality
    if quality == "custom":
        state.awaiting = "custom_crf"
        await query.message.edit_text("🔢 Send a **custom CRF** value (0–51).")
        await query.answer()
        return
    await _start_processing(client, query, state)
    await query.answer()


async def _convert(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    state.data["format"] = parts[1]
    await _start_processing(client, query, state)
    await query.answer()


async def _mres_toggle(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    res = parts[1]
    selected = state.data.setdefault("resolutions", [])
    if res in selected:
        selected.remove(res)
    else:
        selected.append(res)
    await query.message.edit_reply_markup(reply_markup=multires_keyboard(selected))
    await query.answer()


async def _mres_go(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    if not state.data.get("resolutions"):
        await query.answer("Select at least one resolution.", show_alert=True)
        return
    await _start_processing(client, query, state)
    await query.answer()


async def _rms_toggle(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    stype = parts[1]
    selected = state.data.setdefault("stream_types", [])
    if stype in selected:
        selected.remove(stype)
    else:
        selected.append(stype)
    await query.message.edit_reply_markup(reply_markup=remove_streams_keyboard(selected))
    await query.answer()


async def _rms_go(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    if not state.data.get("stream_types"):
        await query.answer("Select at least one stream type.", show_alert=True)
        return
    await _start_processing(client, query, state)
    await query.answer()


async def _extract(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    state.data["format"] = parts[1]
    await _start_processing(client, query, state)
    await query.answer()


async def _wm_type(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    wm_type = parts[1]
    state.data["wm_type"] = wm_type
    if wm_type == "text":
        state.awaiting = "watermark_text"
        await query.message.edit_text("🅰️ Send the **watermark text**.")
    else:
        state.awaiting = "watermark_image"
        await query.message.edit_text("🖼 Send the **watermark image** (photo or file).")
    await query.answer()


async def _wm_pos(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    state.data["position"] = parts[1]
    await query.message.edit_text(
        "🌫 Choose **opacity**:", reply_markup=watermark_opacity_keyboard()
    )
    await query.answer()


async def _wm_op(client, query, parts) -> None:
    state = _require_state(query)
    if state is None:
        await query.answer("Session expired.", show_alert=True)
        return
    state.data["opacity"] = parts[1]
    await _start_processing(client, query, state)
    await query.answer()


async def _task_cancel(client, query, parts) -> None:
    task_id = parts[1]
    cancelled = await queue.cancel(task_id, user_id=query.from_user.id)
    await query.answer("🛑 Task cancelled." if cancelled else "Task not found.", show_alert=True)


async def _settings(client, query, parts) -> None:
    field = parts[1]
    user_id = query.from_user.id
    settings = await db.get_settings(user_id)
    if field == "upload":
        new_value = not settings.upload_as_document
        await db.update_settings(user_id, upload_as_document=new_value)
    elif field in _SETTING_CYCLES:
        attr, choices = _SETTING_CYCLES[field]
        current = getattr(settings, attr)
        if current in choices:
            nxt = choices[(choices.index(current) + 1) % len(choices)]
        else:
            nxt = choices[0]
        await db.update_settings(user_id, **{attr: nxt})
    updated = await db.get_settings(user_id)
    await query.message.edit_reply_markup(reply_markup=settings_keyboard(updated))
    await query.answer("Updated.")


_ROUTES = {
    "menu": _menu,
    "tool": _tool,
    "enc_codec": _enc_codec,
    "enc_q": _enc_quality,
    "conv": _convert,
    "mres_toggle": _mres_toggle,
    "mres_go": _mres_go,
    "rms_toggle": _rms_toggle,
    "rms_go": _rms_go,
    "exa": _extract,
    "exs": _extract,
    "wm_type": _wm_type,
    "wm_pos": _wm_pos,
    "wm_op": _wm_op,
    "task_cancel": _task_cancel,
    "set": _settings,
}
