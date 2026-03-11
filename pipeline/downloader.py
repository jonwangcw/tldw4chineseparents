"""
Download a YouTube video and attempt to extract auto-generated captions.
Falls back gracefully — callers check DownloadResult.transcript for None.

Design:
  - Single yt-dlp call with ignoreerrors=True so subtitle failures (429,
    unavailable) never abort the pipeline.
  - After download, check the video file exists; raise only if video is missing.
  - Audio extracted from the video via local ffmpeg — no second yt-dlp call.

Usage (standalone test):
    python -m pipeline.downloader <youtube_url> <output_dir>
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yt_dlp


@dataclass
class DownloadResult:
    title: str
    transcript: str | None   # None → caller must run Whisper
    audio_path: Path | None  # populated only when transcript is None
    video_path: Path         # always populated (needed for frame extraction)


def run(url: str, tmp_dir: str) -> DownloadResult:
    tmp = Path(tmp_dir)

    title, video_path = _download_video_and_captions(url, tmp)
    transcript = _find_and_parse_captions(tmp)

    audio_path: Path | None = None
    if transcript is None:
        audio_path = _extract_audio_ffmpeg(video_path, tmp)

    return DownloadResult(
        title=title,
        transcript=transcript,
        audio_path=audio_path,
        video_path=video_path,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _download_video_and_captions(url: str, tmp: Path) -> tuple[str, Path]:
    """
    Single yt-dlp call. ignoreerrors=True prevents subtitle errors (e.g. HTTP 429)
    from aborting the download. We verify the video file ourselves afterwards.
    """
    opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/mp4",
        "outtmpl": str(tmp / "video.%(ext)s"),
        "merge_output_format": "mp4",
        # Captions — best-effort
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["zh-Hans", "zh-CN", "zh", "en"],
        "subtitlesformat": "vtt",
        # Never raise on subtitle failures; we check video file existence below
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }

    title = "Untitled Video"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info:
            title = info.get("title", title)

    video_files = [
        f for f in tmp.glob("video.*")
        if f.suffix.lower() not in (".part", ".ytdl")
    ]
    if not video_files:
        raise RuntimeError(
            "视频下载失败。请检查链接是否有效，或该视频是否需要登录才能观看。"
        )
    return title, video_files[0]


def _find_and_parse_captions(tmp: Path) -> str | None:
    """Return parsed plain text from the best VTT file found, or None."""
    vtt_files = sorted(tmp.glob("*.vtt"))
    if not vtt_files:
        return None

    preferred: Path | None = None
    for lang_hint in ("zh-Hans", "zh-CN", "zh"):
        for f in vtt_files:
            if lang_hint in f.name:
                preferred = f
                break
        if preferred:
            break
    caption_file = preferred or vtt_files[0]

    text = _parse_vtt(caption_file)
    return text if text.strip() else None


def _parse_vtt(path: Path) -> str:
    """Convert a WebVTT file to clean plain text."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines: list[str] = []
    prev = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE") or "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or line == prev:
            continue
        if prev.endswith(line):
            continue
        lines.append(line)
        prev = line
    return " ".join(lines)


def _extract_audio_ffmpeg(video_path: Path, tmp: Path) -> Path:
    """Extract MP3 audio from the video using ffmpeg — no network call needed."""
    audio_path = tmp / "audio.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", "128k",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not audio_path.exists():
        raise RuntimeError(f"音频提取失败:\n{result.stderr}")
    return audio_path


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m pipeline.downloader <url> <output_dir>")
        sys.exit(1)
    import os
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    result = run(sys.argv[1], out_dir)
    print(f"Title      : {result.title}")
    print(f"Transcript : {'[found, {} chars]'.format(len(result.transcript)) if result.transcript else 'None (Whisper needed)'}")
    print(f"Audio path : {result.audio_path}")
    print(f"Video path : {result.video_path}")
    if result.transcript:
        print("\n--- Transcript preview (first 500 chars) ---")
        print(result.transcript[:500])
