"""Bridge between collected user state and concrete FFmpeg operations.

Once a flow has gathered everything it needs (the source video plus any extra
inputs/options), :func:`run_tool` builds an :class:`~bot.handlers.processing.Operation`
whose runner downloads the required media and invokes the matching coroutine in
:mod:`bot.ffmpeg.operations`, then schedules it on the global queue.
"""

from __future__ import annotations

from typing import List

from pyrogram import Client
from pyrogram.types import Message

from bot.ffmpeg import operations as ops
from bot.handlers.processing import Operation, download_media, schedule
from bot.helpers.files import make_work_dir
from bot.helpers.progress import ProgressReporter
from bot.utils.logger import get_logger
from bot.utils.state import UserState, state_store

logger = get_logger(__name__)

# Tools that can run as soon as the user picks them / their options, requiring
# no additional uploaded file.
SINGLE_INPUT_TOOLS = {
    "encode",
    "convert",
    "multires",
    "introsub",
    "rm_subs",
    "rm_audio",
    "rm_streams",
    "strip_meta",
    "ex_subs",
    "ex_audio",
}


async def run_tool(
    client: Client,
    chat_id: int,
    user_id: int,
    status_message: Message,
    state: UserState,
) -> None:
    """Build the operation for ``state.tool`` and schedule it for execution."""
    tool = state.tool or ""
    work_dir = make_work_dir(user_id)
    video_msg: Message = state.data["video_msg"]

    async def runner(reporter: ProgressReporter) -> List[str] | str:
        video_path = await download_media(video_msg, work_dir, reporter, "Downloading")
        return await _dispatch(tool, video_path, work_dir, state, reporter)

    operation = Operation(
        tool=tool,
        runner=runner,
        work_dir=work_dir,
        send_as_document=bool(state.data.get("as_document")),
    )
    await schedule(client, user_id, chat_id, status_message, operation)
    state_store.clear(user_id)


async def _dispatch(
    tool: str,
    video_path: str,
    work_dir: str,
    state: UserState,
    reporter: ProgressReporter,
) -> List[str] | str:
    """Download any secondary inputs and call the right FFmpeg operation."""
    data = state.data
    progress = reporter.ffmpeg

    if tool == "encode":
        return await ops.encode(
            video_path,
            codec=data.get("codec", "h264"),
            quality=data.get("quality", "medium"),
            crf=data.get("crf"),
            progress=progress,
        )
    if tool == "convert":
        return await ops.convert(video_path, data["format"], progress=progress)
    if tool == "multires":
        return await ops.multi_resolution(
            video_path, data.get("resolutions", []), progress=progress
        )
    if tool == "introsub":
        return await ops.intro_sub(video_path, progress=progress)
    if tool == "rm_subs":
        return await ops.remove_subs(video_path, progress=progress)
    if tool == "rm_audio":
        return await ops.remove_audio(video_path, progress=progress)
    if tool == "rm_streams":
        return await ops.remove_streams(
            video_path, data.get("stream_types", []), progress=progress
        )
    if tool == "strip_meta":
        return await ops.strip_metadata(video_path, progress=progress)
    if tool == "ex_subs":
        return await ops.extract_subs(video_path, data.get("format", "srt"), progress=progress)
    if tool == "ex_audio":
        return await ops.extract_audio(video_path, data.get("format", "mp3"), progress=progress)

    # ---- multi-input tools -------------------------------------------------
    if tool == "vid_vid":
        second = await download_media(data["video2_msg"], work_dir, reporter, "Downloading #2")
        return await ops.merge_videos(video_path, second, progress=progress)
    if tool == "vid_aud":
        audio = await download_media(data["audio_msg"], work_dir, reporter, "Downloading audio")
        # Keep all of the video's existing streams and append the new audio.
        return await ops.add_audio(
            video_path,
            audio,
            replace=False,
            language=data.get("audio_language"),
            progress=progress,
        )
    if tool == "swap_audio":
        audio = await download_media(data["audio_msg"], work_dir, reporter, "Downloading audio")
        return await ops.swap_audio(
            video_path, audio, language=data.get("audio_language"), progress=progress
        )
    if tool == "vid_sub":
        sub = await download_media(data["sub_msg"], work_dir, reporter, "Downloading subtitle")
        return await ops.add_subtitle(
            video_path, sub, language=data.get("subtitle_language"), progress=progress
        )
    if tool == "vid_aud_sub":
        audio = await download_media(data["audio_msg"], work_dir, reporter, "Downloading audio")
        sub = await download_media(data["sub_msg"], work_dir, reporter, "Downloading subtitle")
        return await ops.add_audio_subtitle(
            video_path,
            audio,
            sub,
            audio_language=data.get("audio_language"),
            subtitle_language=data.get("subtitle_language"),
            progress=progress,
        )
    if tool == "hardsub":
        sub = await download_media(data["sub_msg"], work_dir, reporter, "Downloading subtitle")
        return await ops.hardsub(video_path, sub, progress=progress)
    if tool == "watermark":
        if data.get("wm_type") == "text":
            return await ops.watermark_text(
                video_path,
                data.get("text", "Video Tool Bot"),
                position=data.get("position", "bottom_right"),
                opacity=float(data.get("opacity", 0.7)),
                progress=progress,
            )
        image = await download_media(data["wm_msg"], work_dir, reporter, "Downloading image")
        return await ops.watermark_image(
            video_path,
            image,
            position=data.get("position", "bottom_right"),
            opacity=float(data.get("opacity", 0.7)),
            progress=progress,
        )

    raise ValueError(f"unknown tool: {tool}")


__all__ = ["run_tool", "SINGLE_INPUT_TOOLS"]
