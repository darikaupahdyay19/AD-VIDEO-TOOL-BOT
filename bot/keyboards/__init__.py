"""Inline keyboard factories for the bot's interactive menus.

Callback data follows the convention ``"<namespace>|<value>[|<value>...]"`` so
handlers can dispatch with a simple ``data.split("|")``.  Keeping the payload
small respects Telegram's 64-byte callback-data limit.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Ordered list of the tools shown when a video is received. Each entry is
# ``(label, tool_id)``; ``tool_id`` is embedded in the callback data.
VIDEO_TOOLS: List[Tuple[str, str]] = [
    ("🎞 Encode", "encode"),
    ("🔄 Convert", "convert"),
    ("📐 Multi-Resolution", "multires"),
    ("➕ Video + Video", "vid_vid"),
    ("🎵 Video + Audio", "vid_aud"),
    ("💬 Video + Subtitle", "vid_sub"),
    ("🎬 Video + Audio + Subtitle", "vid_aud_sub"),
    ("📝 IntroSub", "introsub"),
    ("🔥 HardSub", "hardsub"),
    ("🚫 Remove Subs", "rm_subs"),
    ("🔇 Remove Audio", "rm_audio"),
    ("✂️ Remove Streams", "rm_streams"),
    ("🧹 Strip Metadata", "strip_meta"),
    ("📤 Extract Subs", "ex_subs"),
    ("🎧 Extract Audio", "ex_audio"),
    ("🔀 Swap Audio", "swap_audio"),
    ("💧 Watermark", "watermark"),
]


def _grid(
    buttons: Sequence[InlineKeyboardButton], columns: int
) -> List[List[InlineKeyboardButton]]:
    """Arrange ``buttons`` into rows of ``columns`` items."""
    return [list(buttons[i : i + columns]) for i in range(0, len(buttons), columns)]


def _options_keyboard(
    namespace: str,
    options: Iterable[Tuple[str, str]],
    columns: int = 2,
    back: bool = True,
) -> InlineKeyboardMarkup:
    """Build a keyboard from ``(label, value)`` options under ``namespace``."""
    buttons = [
        InlineKeyboardButton(label, callback_data=f"{namespace}|{value}")
        for label, value in options
    ]
    rows = _grid(buttons, columns)
    footer = []
    if back:
        footer.append(InlineKeyboardButton("⬅️ Back", callback_data="menu|main"))
    footer.append(InlineKeyboardButton("❌ Cancel", callback_data="menu|cancel"))
    rows.append(footer)
    return InlineKeyboardMarkup(rows)


def video_tools_keyboard() -> InlineKeyboardMarkup:
    """The main tool menu shown when a user sends a video."""
    buttons = [
        InlineKeyboardButton(label, callback_data=f"tool|{tool_id}")
        for label, tool_id in VIDEO_TOOLS
    ]
    rows = _grid(buttons, 2)
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="menu|cancel")])
    return InlineKeyboardMarkup(rows)


def encode_codec_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "enc_codec",
        [("H264", "h264"), ("H265", "h265"), ("AV1", "av1"), ("VP9", "vp9")],
    )


def encode_quality_keyboard(codec: str) -> InlineKeyboardMarkup:
    return _options_keyboard(
        "enc_q",
        [
            ("Low", f"{codec}|low"),
            ("Medium", f"{codec}|medium"),
            ("High", f"{codec}|high"),
            ("Custom CRF", f"{codec}|custom"),
        ],
    )


def convert_format_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "conv",
        [
            ("MP4", "mp4"),
            ("MKV", "mkv"),
            ("AVI", "avi"),
            ("MOV", "mov"),
            ("WEBM", "webm"),
        ],
    )


def multires_keyboard(selected: Iterable[str]) -> InlineKeyboardMarkup:
    """Toggleable multi-resolution selector. ``selected`` is currently chosen."""
    selected_set = set(selected)
    resolutions = ["240p", "360p", "480p", "720p", "1080p"]
    buttons = []
    for res in resolutions:
        mark = "✅ " if res in selected_set else ""
        buttons.append(
            InlineKeyboardButton(f"{mark}{res}", callback_data=f"mres_toggle|{res}")
        )
    rows = _grid(buttons, 3)
    rows.append(
        [
            InlineKeyboardButton("🚀 Generate", callback_data="mres_go|run"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu|cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def remove_streams_keyboard(selected: Iterable[str]) -> InlineKeyboardMarkup:
    selected_set = set(selected)
    types = [
        ("Audio", "audio"),
        ("Subtitle", "subtitle"),
        ("Data", "data"),
        ("Attachment", "attachment"),
    ]
    buttons = []
    for label, value in types:
        mark = "✅ " if value in selected_set else ""
        buttons.append(
            InlineKeyboardButton(f"{mark}{label}", callback_data=f"rms_toggle|{value}")
        )
    rows = _grid(buttons, 2)
    rows.append(
        [
            InlineKeyboardButton("🚀 Remove", callback_data="rms_go|run"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu|cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def extract_audio_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "exa",
        [("MP3", "mp3"), ("AAC", "aac"), ("FLAC", "flac"), ("WAV", "wav")],
    )


def extract_subs_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "exs", [("SRT", "srt"), ("ASS", "ass"), ("VTT", "vtt")]
    )


def audio_format_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "audfmt",
        [("MP3", "mp3"), ("AAC", "aac"), ("FLAC", "flac"), ("M4A", "m4a")],
    )


def subtitle_format_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "subfmt", [("SRT", "srt"), ("ASS", "ass"), ("VTT", "vtt")]
    )


def watermark_type_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "wm_type", [("🖼 Image", "image"), ("🅰️ Text", "text")]
    )


def watermark_position_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "wm_pos",
        [
            ("Top Left", "top_left"),
            ("Top Right", "top_right"),
            ("Bottom Left", "bottom_left"),
            ("Bottom Right", "bottom_right"),
            ("Center", "center"),
        ],
    )


def watermark_opacity_keyboard() -> InlineKeyboardMarkup:
    return _options_keyboard(
        "wm_op",
        [("30%", "0.3"), ("50%", "0.5"), ("70%", "0.7"), ("100%", "1.0")],
        columns=4,
    )


def settings_keyboard(settings) -> InlineKeyboardMarkup:
    """Build the settings menu reflecting the user's current preferences."""
    upload_label = "Document" if settings.upload_as_document else "Video"
    rows = [
        [InlineKeyboardButton(f"Codec: {settings.video_codec}", callback_data="set|codec")],
        [InlineKeyboardButton(f"CRF: {settings.crf}", callback_data="set|crf")],
        [InlineKeyboardButton(f"Preset: {settings.preset}", callback_data="set|preset")],
        [InlineKeyboardButton(f"Format: {settings.output_format}", callback_data="set|format")],
        [InlineKeyboardButton(f"Upload as: {upload_label}", callback_data="set|upload")],
        [InlineKeyboardButton("✅ Close", callback_data="menu|close")],
    ]
    return InlineKeyboardMarkup(rows)


def cancel_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """A single 'Cancel' button bound to a running ``task_id``."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🛑 Cancel Task", callback_data=f"task_cancel|{task_id}")]]
    )


__all__ = [
    "VIDEO_TOOLS",
    "video_tools_keyboard",
    "encode_codec_keyboard",
    "encode_quality_keyboard",
    "convert_format_keyboard",
    "multires_keyboard",
    "remove_streams_keyboard",
    "extract_audio_keyboard",
    "extract_subs_keyboard",
    "audio_format_keyboard",
    "subtitle_format_keyboard",
    "watermark_type_keyboard",
    "watermark_position_keyboard",
    "watermark_opacity_keyboard",
    "settings_keyboard",
    "cancel_task_keyboard",
]
