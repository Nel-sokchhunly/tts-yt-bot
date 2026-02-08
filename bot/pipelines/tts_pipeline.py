"""TTS from SRT, stretch to video duration, replace video audio."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import edge_tts

# Optional cap (seconds) for testing: only process first N seconds of video. Set VIDEO_CAP_SEC in env.
VIDEO_CAP_SEC_ENV = "VIDEO_CAP_SEC"

# SRT timestamp line: 00:00:11,800 --> 00:00:13,199
SRT_TIMING = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
DEFAULT_VOICE = "en-US-GuyNeural"


def _srt_timestamp_to_sec(match, start: bool) -> float:
    """Convert SRT timestamp group to seconds. start=True uses groups 1-4, else 5-8."""
    base = 0 if start else 4
    h, m, s, ms = (int(match.group(base + 1)), int(match.group(base + 2)),
                   int(match.group(base + 3)), int(match.group(base + 4)))
    return h * 3600 + m * 60 + s + ms / 1000.0


def _parse_srt_cues(path: str) -> list[tuple[float, float, str]]:
    """Parse SRT into list of (start_sec, end_sec, text) per cue."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.strip().replace("\r", "").split("\n")
    cues = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line.isdigit():
            if i >= len(lines):
                break
            timing_line = lines[i].strip()
            i += 1
            m = SRT_TIMING.search(timing_line)
            if not m:
                continue
            start_sec = _srt_timestamp_to_sec(m, True)
            end_sec = _srt_timestamp_to_sec(m, False)
            parts = []
            while i < len(lines) and lines[i].strip():
                parts.append(lines[i].strip())
                i += 1
            i += 1
            cue_text = " ".join(parts)
            if cue_text:
                cues.append((start_sec, end_sec, cue_text))
    return cues


def _group_cues_into_blocks(
    cues: list[tuple[float, float, str]],
    max_gap_sec: float = 0.8,
    max_block_duration_sec: float = 30.0,
) -> list[tuple[float, float, str]]:
    """Group consecutive cues into speech blocks. A new block starts when gap > max_gap_sec
    or block would exceed max_block_duration_sec. Returns list of (start_sec, end_sec, text)."""
    if not cues:
        return []
    blocks = []
    block_start, block_end, parts = cues[0][0], cues[0][1], [cues[0][2]]
    for i in range(1, len(cues)):
        start_sec, end_sec, text = cues[i]
        gap = start_sec - block_end
        # New block if gap is large or adding this cue would exceed max block duration
        if gap > max_gap_sec or (end_sec - block_start > max_block_duration_sec):
            blocks.append((block_start, block_end, " ".join(parts)))
            block_start, block_end, parts = start_sec, end_sec, [text]
        else:
            block_end = end_sec
            parts.append(text)
    blocks.append((block_start, block_end, " ".join(parts)))
    return blocks


def _parse_srt(path: str) -> str:
    """Extract full text from SRT (all cues joined with space)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")
    parts = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line.isdigit():
            # next line is timing, then text
            if i < len(lines) and SRT_TIMING.search(lines[i]):
                i += 1
            while i < len(lines) and lines[i].strip():
                parts.append(lines[i].strip())
                i += 1
            i += 1
    return " ".join(parts)


def _duration_seconds(media_path: str) -> float:
    """Get duration in seconds via ffprobe."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            media_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def _generate_tts(text: str, out_path: str, voice: str = DEFAULT_VOICE) -> None:
    """Generate TTS to file (run from sync context via asyncio.run or from async)."""
    import asyncio
    async def _do():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)
    asyncio.run(_do())


def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """Split text into chunks by size, trying not to cut mid-sentence."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # try to break at sentence or word
            for sep in (". ", "! ", "? ", " "):
                last = text.rfind(sep, start, end + 1)
                if last != -1:
                    end = last + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def _concat_audio(paths: list[str], out_path: str) -> None:
    """Concatenate audio files with ffmpeg concat demuxer."""
    list_path = Path(out_path).parent / "_concat_list.txt"
    list_path.write_text(
        "\n".join(f"file '{Path(p).absolute()}'" for p in paths),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy", out_path,
        ],
        capture_output=True,
        check=True,
    )
    list_path.unlink(missing_ok=True)


def _create_silence(duration_sec: float, out_path: str, sample_rate: int = 24000) -> None:
    """Create a silent audio file of given duration (seconds)."""
    if duration_sec <= 0:
        return
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anullsrc=r={sample_rate}:cl=mono",
            "-t", str(duration_sec),
            "-q:a", "9", out_path,
        ],
        capture_output=True,
        check=True,
    )


def _stretch_audio(
    audio_path: str,
    out_path: str,
    target_duration_sec: float,
    max_atempo: float = 1.2,
) -> None:
    """Stretch/speed audio toward target_duration_sec. Caps speed-up at max_atempo (e.g. 1.2x)
    so voice doesn't sound too fast. Does not trim here; caller trims only if overlap."""
    current = _duration_seconds(audio_path)
    if current <= 0:
        raise ValueError("TTS audio has zero duration")
    ratio = current / target_duration_sec
    effective_ratio = min(ratio, max_atempo)
    filters = []
    r = effective_ratio
    while r > 2.0:
        filters.append("atempo=2.0")
        r /= 2.0
    while r < 0.5:
        filters.append("atempo=0.5")
        r /= 0.5
    filters.append(f"atempo={r}")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-filter:a", ",".join(filters),
            "-vn", out_path,
        ],
        capture_output=True,
        check=True,
    )


def _trim_audio(audio_path: str, out_path: str, max_duration_sec: float) -> None:
    """Trim audio to at most max_duration_sec (only if longer)."""
    current = _duration_seconds(audio_path)
    if current <= max_duration_sec:
        if audio_path != out_path:
            shutil.copy2(audio_path, out_path)
        return
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", audio_path,
            "-t", str(max_duration_sec),
            "-c", "copy", out_path,
        ],
        capture_output=True,
        check=True,
    )


def _replace_video_audio(
    video_path: str,
    audio_path: str,
    out_path: str,
    max_duration_sec: float | None = None,
) -> None:
    """Replace video audio track with audio_path; write to out_path.
    If max_duration_sec is set, output is trimmed to that length (for testing cap)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
    ]
    if max_duration_sec is not None and max_duration_sec > 0:
        cmd.extend(["-t", str(max_duration_sec)])
    cmd.append(out_path)
    subprocess.run(cmd, capture_output=True, check=True)


def run_tts_and_replace(
    srt_path: str,
    video_path: str,
    out_dir: str,
    progress_state: dict | None = None,
) -> str:
    """
    TTS from SRT: group cues into speech blocks, TTS each block as one, stretch
    block TTS to match block time span (first seg start to last seg end), place
    with silence gaps. Trim only if block would overlap next block.
    Returns path to the dubbed video.
    """
    def _set_phase(msg: str) -> None:
        if progress_state is not None:
            progress_state["tts_phase"] = msg

    def _set_percent(pct: float) -> None:
        if progress_state is not None:
            progress_state["tts_percent"] = min(100.0, max(0.0, pct))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = Path(video_path)
    base = video_path.stem
    tts_raw = out_dir / f"{base}_tts_raw.mp3"
    dubbed = out_dir / f"{base}_dubbed.mp4"
    video_duration = _duration_seconds(str(video_path))
    cap_sec = None
    raw = os.environ.get(VIDEO_CAP_SEC_ENV, "").strip()
    if raw:
        try:
            cap_sec = float(raw)
        except ValueError:
            pass
    effective_duration = min(video_duration, cap_sec) if cap_sec and cap_sec > 0 else video_duration

    _set_phase("Parsing SRT...")
    _set_percent(0)
    cues = _parse_srt_cues(srt_path)
    if not cues:
        raise ValueError("SRT has no cues")
    if effective_duration < video_duration:
        cues = [c for c in cues if c[0] < effective_duration]
        if not cues:
            raise ValueError("No cues within cap duration")
    blocks = _group_cues_into_blocks(cues)
    n = len(blocks)
    merged_path = out_dir / f"{base}_tts_merged.mp3"
    block_path = out_dir / f"{base}_tts_block.mp3"
    block_stretched_path = out_dir / f"{base}_tts_block_str.mp3"
    block_trimmed_path = out_dir / f"{base}_tts_block_trim.mp3"
    silence_path = out_dir / f"{base}_tts_silence.mp3"
    tmp_merged_path = out_dir / f"{base}_tts_merged_tmp.mp3"
    min_block_sec = 0.2
    # Track where the timeline actually ends after each block (so next gap is correct when we trim)
    timeline_end_sec = 0.0

    for i, (block_start, block_end, text) in enumerate(blocks):
        _set_phase(f"TTS block {i + 1}/{n}...")
        _set_percent(100 * (i + 0.5) / n)
        block_duration = max(min_block_sec, block_end - block_start)
        # Long block text: chunk and concat TTS, then stretch whole block to fit
        text_chunks = _chunk_text(text)
        if len(text_chunks) == 1:
            _generate_tts(text, str(block_path))
        else:
            for j, chunk in enumerate(text_chunks):
                cp = out_dir / f"{base}_tts_c{j}.mp3"
                _generate_tts(chunk, str(cp))
            _concat_audio([str(out_dir / f"{base}_tts_c{k}.mp3") for k in range(len(text_chunks))], str(block_path))
            for k in range(len(text_chunks)):
                (out_dir / f"{base}_tts_c{k}.mp3").unlink(missing_ok=True)
        _stretch_audio(str(block_path), str(block_stretched_path), block_duration)
        next_block_start = blocks[i + 1][0] if i < n - 1 else effective_duration
        max_duration = next_block_start - block_start
        _trim_audio(str(block_stretched_path), str(block_trimmed_path), max_duration)
        # Gap from actual end of previous content to this block start (avoids next block starting late)
        gap_before = block_start - timeline_end_sec
        to_concat = []
        if gap_before > 0.01:
            _create_silence(gap_before, str(silence_path))
            to_concat.append(str(silence_path))
        to_concat.append(str(block_trimmed_path))
        if i == 0:
            _concat_audio(to_concat, str(merged_path))
        else:
            _concat_audio([str(merged_path)] + to_concat, str(tmp_merged_path))
            merged_path.unlink(missing_ok=True)
            tmp_merged_path.rename(merged_path)
        segment_duration = _duration_seconds(str(block_trimmed_path))
        timeline_end_sec = block_start + segment_duration
        block_path.unlink(missing_ok=True)
        block_stretched_path.unlink(missing_ok=True)
        block_trimmed_path.unlink(missing_ok=True)
        _set_percent(100 * (i + 1) / n)

    trail = effective_duration - timeline_end_sec
    if trail > 0.01:
        _set_phase("Finalizing timeline...")
        _create_silence(trail, str(silence_path))
        _concat_audio([str(merged_path), str(silence_path)], str(tmp_merged_path))
        merged_path.unlink(missing_ok=True)
        tmp_merged_path.rename(merged_path)
    silence_path.unlink(missing_ok=True)
    merged_path.rename(tts_raw)

    _set_phase("Replacing video audio...")
    _set_percent(98)
    _replace_video_audio(
        str(video_path),
        str(tts_raw),
        str(dubbed),
        max_duration_sec=effective_duration if effective_duration < video_duration else None,
    )
    _set_percent(100)

    return str(dubbed)
