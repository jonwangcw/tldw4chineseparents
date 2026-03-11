"""
Extract keyframes from a video using ffmpeg scene-change detection.

Strategy:
  1. Try scene-change threshold 0.3 → collect JPEGs
  2. If 0 frames: retry with threshold 0.15
  3. If still 0: fall back to 1 frame per 60 seconds (fps=1/60)
  4. Uniformly subsample down to MAX_FRAMES (30) if over the cap

Usage (standalone test):
    python -m pipeline.frames <video_path> <output_dir>
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAX_FRAMES = 30
_SCALE = "scale=768:432"


def extract(video_path: Path | str, tmp_dir: str) -> list[Path]:
    video_path = Path(video_path)
    out_dir = Path(tmp_dir) / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = _scene_detect(video_path, out_dir, threshold=0.3)
    if not frames:
        frames = _scene_detect(video_path, out_dir, threshold=0.15)
    if not frames:
        frames = _fps_fallback(video_path, out_dir)

    frames = sorted(frames)  # ensure chronological order
    return _subsample(frames, MAX_FRAMES)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scene_detect(video: Path, out_dir: Path, threshold: float) -> list[Path]:
    pattern = str(out_dir / f"scene_{threshold:.2f}_%04d.jpg")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vf", f"select='gt(scene,{threshold})',{_SCALE}",
        "-vsync", "vfr",
        "-q:v", "3",
        pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # ffmpeg returns non-zero even on success sometimes; check file output
    frames = sorted(out_dir.glob(f"scene_{threshold:.2f}_*.jpg"))
    return frames


def _fps_fallback(video: Path, out_dir: Path) -> list[Path]:
    """Extract one frame per minute as a last resort."""
    pattern = str(out_dir / "fallback_%04d.jpg")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-vf", f"fps=1/60,{_SCALE}",
        "-q:v", "3",
        pattern,
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    return sorted(out_dir.glob("fallback_*.jpg"))


def _subsample(frames: list[Path], cap: int) -> list[Path]:
    """Uniformly subsample to at most `cap` frames, keeping first and last."""
    if len(frames) <= cap:
        return frames
    indices = [round(i * (len(frames) - 1) / (cap - 1)) for i in range(cap)]
    # deduplicate while preserving order
    seen: set[int] = set()
    result: list[Path] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            result.append(frames[idx])
    return result


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m pipeline.frames <video_path> <output_dir>")
        sys.exit(1)
    video = Path(sys.argv[1])
    out = sys.argv[2]
    result = extract(video, out)
    print(f"Extracted {len(result)} frames:")
    for f in result:
        print(f"  {f}")
