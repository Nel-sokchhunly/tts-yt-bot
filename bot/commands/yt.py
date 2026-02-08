"""Handle /yt <url>: reply processing, download, then done."""

import asyncio
import glob
import os
import re
from pathlib import Path

import yt_dlp
from telegram import InputFile, Update
from telegram.ext import ContextTypes

from bot.stores.processing_store import (
    add as processing_add,
    remove as processing_remove,
    update_paths as processing_update_paths,
)
from bot.pipelines.tts_pipeline import run_tts_and_replace

# Match common YouTube URL forms
YT_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[^\s]+",
    re.IGNORECASE,
)


def _extract_yt_url(text: str) -> str | None:
    m = YT_URL_PATTERN.search(text.strip())
    return m.group(0) if m else None


def _progress_hook(progress_state: dict, key: str):
    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total and total > 0:
                progress_state[key] = min(100, 100 * (d.get("downloaded_bytes") or 0) / total)
        elif d.get("status") == "finished":
            progress_state[key] = 100
    return hook


def _download_video(
    url: str, out_dir: str, progress_state: dict | None = None, progress_key: str = "video_percent"
) -> tuple[str, str]:
    """Download video only; return (video_path, video_id). Skip if already present."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    opts_no_dl = {"quiet": True}
    with yt_dlp.YoutubeDL(opts_no_dl) as ydl:
        info = ydl.extract_info(url, download=False)
    video_id = info["id"]
    video_candidates = [
        p for p in glob.glob(os.path.join(out_dir, f"{video_id}.*"))
        if not p.endswith(".srt") and not p.endswith(".vtt")
    ]
    if video_candidates:
        if progress_state is not None:
            progress_state[progress_key] = 100
        return (video_candidates[0], video_id)
    opts = {
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "quiet": True,
    }
    if progress_state is not None:
        opts["progress_hooks"] = [_progress_hook(progress_state, progress_key)]
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
    video_candidates = [
        p for p in glob.glob(os.path.join(out_dir, f"{video_id}.*"))
        if not p.endswith(".srt") and not p.endswith(".vtt")
    ]
    video_path = video_candidates[0] if video_candidates else ""
    return (video_path, video_id)


def _download_srt(
    url: str, out_dir: str, progress_state: dict | None = None, progress_key: str = "srt_percent"
) -> str | None:
    """Download SRT only; return srt_path or None. Skip if already present."""
    out_dir = os.path.abspath(out_dir)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    opts_no_dl = {"quiet": True}
    with yt_dlp.YoutubeDL(opts_no_dl) as ydl:
        info = ydl.extract_info(url, download=False)
    video_id = info["id"]
    for ext in ("srt", "vtt"):
        p = os.path.join(out_dir, f"{video_id}.en.{ext}")
        if os.path.isfile(p):
            if progress_state is not None:
                progress_state[progress_key] = 100
            return p
    for f in os.listdir(out_dir):
        if f.startswith(video_id) and (f.endswith(".srt") or f.endswith(".vtt")):
            if progress_state is not None:
                progress_state[progress_key] = 100
            return os.path.join(out_dir, f)
    opts = {
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "paths": {"home": out_dir, "temp": out_dir},
        "quiet": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "srt",
        "subtitleslangs": ["en"],
    }
    if progress_state is not None:
        opts["progress_hooks"] = [_progress_hook(progress_state, progress_key)]
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
    for ext in ("srt", "vtt"):
        p = os.path.join(out_dir, f"{video_id}.en.{ext}")
        if os.path.isfile(p):
            return p
    for f in os.listdir(out_dir):
        if f.startswith(video_id) and (f.endswith(".srt") or f.endswith(".vtt")):
            return os.path.join(out_dir, f)
    return None


def _format_progress(state: dict) -> str:
    if state.get("error"):
        return f"Failed: {state['error']}"
    if state.get("stage") == "download":
        v = state.get("video_percent")
        s = state.get("srt_percent")
        v_str = f"{v:.0f}%" if v is not None else "..."
        s_str = f"{s:.0f}%" if s is not None else "..."
        return f"Video: {v_str}\nSRT: {s_str}"
    if state.get("stage") == "tts":
        phase = state.get("tts_phase") or "..."
        pct = state.get("tts_percent")
        pct_str = f" {pct:.0f}%" if pct is not None else ""
        return f"Video and SRT downloaded.\nTTS: {phase}{pct_str}"
    return "Processing..."


async def _progress_updater(progress_msg, progress_state: dict, interval: float = 1.5) -> None:
    """Periodically edit progress_msg with progress_state until done or error."""
    while not progress_state.get("done") and not progress_state.get("error"):
        try:
            text = _format_progress(progress_state)
            await progress_msg.edit_text(text)
        except Exception:
            pass
        await asyncio.sleep(interval)
    try:
        await progress_msg.edit_text(_format_progress(progress_state))
    except Exception:
        pass


async def handle_yt_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if not context.args:
        await update.message.reply_text("Usage: /yt <youtube_url>")
        return
    url = _extract_yt_url(context.args[0])
    if not url:
        await update.message.reply_text("Invalid YouTube URL.")
        return
    chat_id = update.message.chat_id
    user_id = update.effective_user.id

    processing_add(chat_id, user_id, url)
    progress_state = {
        "stage": "download",
        "video_percent": None,
        "srt_percent": None,
        "tts_phase": None,
        "tts_percent": None,
        "done": False,
        "error": None,
    }
    try:
        progress_msg = await update.message.reply_text("Processing...")
        updater_task = asyncio.create_task(
            _progress_updater(progress_msg, progress_state)
        )
        data_dir = os.environ.get("DATA_DIR", "/app/data")
        out_dir = os.path.join(data_dir, "downloads")
        try:
            (video_path, _), srt_path = await asyncio.gather(
                asyncio.to_thread(
                    _download_video, url, out_dir, progress_state, "video_percent"
                ),
                asyncio.to_thread(
                    _download_srt, url, out_dir, progress_state, "srt_percent"
                ),
            )
            processing_update_paths(chat_id, url, video_path, srt_path)
            progress_state["stage"] = "tts"
            dubbed_path = ""
            if video_path and srt_path:
                dubbed_path = await asyncio.to_thread(
                    run_tts_and_replace,
                    srt_path,
                    video_path,
                    out_dir,
                    progress_state,
                )
            progress_state["done"] = True
            await updater_task
            send_video = os.environ.get("SEND_VIDEO_AFTER_DONE", "").strip().lower() in ("1", "true", "yes")
            if dubbed_path and send_video:
                with open(dubbed_path, "rb") as f:
                    video_file = InputFile(f, filename=os.path.basename(dubbed_path))
                await update.message.reply_video(
                    video=video_file,
                    caption="TTS done. Video dubbed.",
                    read_timeout=90,
                    write_timeout=120,
                )
            else:
                await update.message.reply_text(
                    "TTS done. Video dubbed." if dubbed_path else "TTS skipped (no video or SRT)."
                )
        except Exception as e:
            progress_state["error"] = str(e)[:400]
            progress_state["done"] = True
            await updater_task
            await update.message.reply_text(f"Failed: {progress_state['error']}")
    finally:
        processing_remove(chat_id, url)
