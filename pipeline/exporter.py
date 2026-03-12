"""
Convert a markdown-formatted Chinese summary to a PDF using fpdf2.

Supports the fixed markdown structure produced by analyzer.summarize():
  **Header**         → bold 14pt section header
  • Bullet point     → indented body text
  Paragraph text     → normal body text
  Blank line         → vertical spacing

Requires NotoSansSC-Regular.ttf and NotoSansSC-Bold.ttf in assets/.

Usage (standalone test):
    python -m pipeline.exporter <markdown_file> <output.pdf>
"""
from __future__ import annotations

import sys
from pathlib import Path

from fpdf import FPDF

# Resolve assets directory relative to this file (works regardless of cwd)
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_FONT_REGULAR = _ASSETS_DIR / "NotoSansSC-Regular.ttf"
_FONT_BOLD = _ASSETS_DIR / "NotoSansSC-Bold.ttf"

_PAGE_MARGIN_MM = 20
_BODY_FONT_SIZE = 12
_HEADER_FONT_SIZE = 14
_LINE_HEIGHT = 7
_HEADER_LINE_HEIGHT = 8
_BULLET_INDENT_MM = 6


def to_pdf(markdown_text: str, title: str = "") -> bytes:
    """Render markdown_text as a PDF and return the raw bytes."""
    _check_fonts()

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(_PAGE_MARGIN_MM, _PAGE_MARGIN_MM, _PAGE_MARGIN_MM)
    pdf.set_auto_page_break(auto=True, margin=_PAGE_MARGIN_MM)
    pdf.add_page()

    # Register fonts
    pdf.add_font("NotoSansSC", style="", fname=str(_FONT_REGULAR))
    pdf.add_font("NotoSansSC", style="B", fname=str(_FONT_BOLD))

    # Document metadata
    pdf.set_title(title or "视频摘要")
    pdf.set_author("视频摘要助手")
    pdf.set_creator("tldw4chineseparents")

    # Optional title at top of page
    if title:
        pdf.set_font("NotoSansSC", style="B", size=16)
        pdf.multi_cell(0, 10, title, align="C")
        pdf.ln(4)

    _render_markdown(pdf, markdown_text)

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _render_markdown(pdf: FPDF, text: str) -> None:
    pdf.set_font("NotoSansSC", style="", size=_BODY_FONT_SIZE)
    left_margin = pdf.l_margin

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            # Blank line → small vertical gap
            pdf.ln(3)
            continue

        # Bold header: **text** (entire line wrapped in **)
        if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
            header_text = stripped[2:-2]
            pdf.ln(3)
            pdf.set_font("NotoSansSC", style="B", size=_HEADER_FONT_SIZE)
            pdf.set_x(left_margin)
            pdf.multi_cell(0, _HEADER_LINE_HEIGHT, header_text)
            pdf.set_font("NotoSansSC", style="", size=_BODY_FONT_SIZE)
            continue

        # Bullet point: starts with • or -
        if stripped.startswith("•") or stripped.startswith("-"):
            bullet_text = stripped.lstrip("•- ").strip()
            # Use U+2022 bullet to ensure consistent rendering
            display = "\u2022  " + bullet_text
            pdf.set_x(left_margin + _BULLET_INDENT_MM)
            pdf.multi_cell(0, _LINE_HEIGHT, display)
            pdf.set_x(left_margin)
            continue

        # Normal paragraph text
        pdf.set_x(left_margin)
        pdf.multi_cell(0, _LINE_HEIGHT, stripped)


def _check_fonts() -> None:
    if _FONT_REGULAR.exists() and _FONT_BOLD.exists():
        return
    # Attempt automatic download before failing
    try:
        import importlib.util, subprocess, sys
        script = Path(__file__).parent.parent / "scripts" / "download_fonts.py"
        subprocess.run([sys.executable, str(script)], check=True, encoding="utf-8")
    except Exception:
        pass
    missing = [str(f) for f in (_FONT_REGULAR, _FONT_BOLD) if not f.exists()]
    if missing:
        raise FileNotFoundError(
            "CJK font files not found. Run: python scripts/download_fonts.py\n"
            "Or download NotoSansSC-Regular.ttf and NotoSansSC-Bold.ttf from "
            "https://fonts.google.com/noto/specimen/Noto+Sans+SC "
            f"and place them in: {_ASSETS_DIR}\n\nMissing: {', '.join(missing)}"
        )


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m pipeline.exporter <markdown_file> <output.pdf>")
        sys.exit(1)
    md_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    out_path = Path(sys.argv[2])
    pdf_bytes = to_pdf(md_text, title="测试摘要")
    out_path.write_bytes(pdf_bytes)
    print(f"PDF written to {out_path} ({len(pdf_bytes):,} bytes)")
