"""
Transcribe audio using the OpenAI Whisper API.

Handles files larger than 20 MB by splitting on silence boundaries (pydub).
Falls back to time-based splitting if no silences are detected.

Usage (standalone test):
    python -m pipeline.transcriber <audio_path>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import openai
from pydub import AudioSegment
from pydub.silence import split_on_silence

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB safety margin (API limit is 25 MB)
_TARGET_CHUNK_BYTES = 18 * 1024 * 1024  # aim for ~18 MB per chunk
_CHUNK_DURATION_MS = 10 * 60 * 1000  # 10-minute time-based fallback chunks


def run(audio_path: Path | str) -> str:
    audio_path = Path(audio_path)
    size = audio_path.stat().st_size

    client = openai.OpenAI()  # reads OPENAI_API_KEY from env

    if size <= _MAX_BYTES:
        return _transcribe_file(client, audio_path)

    # File too large — split into chunks
    chunks = _split_audio(audio_path)
    parts: list[str] = []
    tmp_dir = audio_path.parent / "whisper_chunks"
    tmp_dir.mkdir(exist_ok=True)
    for i, chunk in enumerate(chunks):
        chunk_path = tmp_dir / f"chunk_{i:03d}.mp3"
        chunk.export(str(chunk_path), format="mp3", bitrate="128k")
        parts.append(_transcribe_file(client, chunk_path))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _transcribe_file(client: openai.OpenAI, path: Path) -> str:
    with open(path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
            language=None,  # auto-detect language
        )
    # response is a plain string when response_format="text"
    return str(response).strip()


def _split_audio(audio_path: Path) -> list[AudioSegment]:
    """Split audio at silence boundaries; fall back to time-based if needed."""
    audio = AudioSegment.from_mp3(str(audio_path))

    silence_chunks = split_on_silence(
        audio,
        min_silence_len=700,
        silence_thresh=-40,
        keep_silence=300,
        seek_step=10,
    )

    if len(silence_chunks) <= 1:
        # No meaningful silences found — use time-based splitting
        return _time_split(audio)

    return _merge_to_target(silence_chunks)


def _time_split(audio: AudioSegment) -> list[AudioSegment]:
    """Split audio into fixed-duration chunks."""
    chunks: list[AudioSegment] = []
    start = 0
    total = len(audio)
    while start < total:
        end = min(start + _CHUNK_DURATION_MS, total)
        chunks.append(audio[start:end])
        start = end
    return chunks


def _merge_to_target(chunks: list[AudioSegment]) -> list[AudioSegment]:
    """
    Merge pydub silence-split chunks until each group approaches
    _TARGET_CHUNK_BYTES (estimated from duration + 128 kbps bitrate).
    """
    # bytes per ms at 128 kbps: 128_000 bits/s / 8 / 1000 = 16 bytes/ms
    bytes_per_ms = 16

    merged: list[AudioSegment] = []
    current = AudioSegment.empty()
    current_bytes = 0

    for chunk in chunks:
        chunk_bytes = len(chunk) * bytes_per_ms
        if current_bytes + chunk_bytes > _TARGET_CHUNK_BYTES and len(current) > 0:
            merged.append(current)
            current = chunk
            current_bytes = chunk_bytes
        else:
            current = current + chunk
            current_bytes += chunk_bytes

    if len(current) > 0:
        merged.append(current)

    return merged


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.transcriber <audio_path>")
        sys.exit(1)
    from dotenv import load_dotenv
    load_dotenv()
    transcript = run(Path(sys.argv[1]))
    print(f"Transcript length: {len(transcript)} chars")
    print("\n--- Preview (first 500 chars) ---")
    print(transcript[:500])
