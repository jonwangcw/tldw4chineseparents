"""
Download NotoSansSC-Regular.ttf and NotoSansSC-Bold.ttf into assets/.

Uses the Google Fonts CSS API with a legacy User-Agent that forces TTF
responses instead of woff2. Safe to run repeatedly — skips files already
present.

Usage:
    python scripts/download_fonts.py
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

_ASSETS_DIR = Path(__file__).parent.parent / "assets"

# Google Fonts CSS endpoint — legacy UA forces TTF responses
_FONTS_CSS_URL = "https://fonts.googleapis.com/css?family=Noto+Sans+SC:400,700"
_LEGACY_UA = (
    "Mozilla/5.0 (Windows NT 6.1) "
    "AppleWebKit/534.30 (KHTML, like Gecko) "
    "Chrome/12.0.742.112 Safari/534.30"
)

_TARGETS = {
    "NotoSansSC-Regular.ttf": "400",
    "NotoSansSC-Bold.ttf": "700",
}


def main() -> None:
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    already_have = [name for name in _TARGETS if (_ASSETS_DIR / name).exists()]
    if len(already_have) == len(_TARGETS):
        print("Fonts already present — nothing to download.")
        return

    print("Fetching font URLs from Google Fonts…")
    css = _fetch_css()

    # Parse CSS: each @font-face block contains font-weight and a url(...)
    blocks = re.split(r"@font-face\s*\{", css)
    url_map: dict[str, str] = {}  # weight → ttf url
    for block in blocks:
        weight_m = re.search(r"font-weight:\s*(\d+)", block)
        url_m = re.search(r"url\((https://[^)]+\.ttf)\)", block)
        if weight_m and url_m:
            url_map[weight_m.group(1)] = url_m.group(1)

    if not url_map:
        print("ERROR: Could not parse font URLs from Google Fonts CSS.")
        print("Please download the fonts manually from:")
        print("  https://fonts.google.com/noto/specimen/Noto+Sans+SC")
        print(f"  Place NotoSansSC-Regular.ttf and NotoSansSC-Bold.ttf in: {_ASSETS_DIR}")
        sys.exit(1)

    weight_to_file = {"400": "NotoSansSC-Regular.ttf", "700": "NotoSansSC-Bold.ttf"}
    for weight, filename in weight_to_file.items():
        dest = _ASSETS_DIR / filename
        if dest.exists():
            print(f"  {filename} already present, skipping.")
            continue
        url = url_map.get(weight)
        if not url:
            print(f"  WARNING: No URL found for weight {weight}, skipping {filename}.")
            continue
        print(f"  Downloading {filename}…", end=" ", flush=True)
        urllib.request.urlretrieve(url, dest)
        print(f"done ({dest.stat().st_size // 1024} KB)")

    print("Font download complete.")


def _fetch_css() -> str:
    req = urllib.request.Request(_FONTS_CSS_URL, headers={"User-Agent": _LEGACY_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


if __name__ == "__main__":
    main()
