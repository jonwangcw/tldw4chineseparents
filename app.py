"""
tldw4chineseparents — Streamlit entry point.

Run with:
    streamlit run app.py
"""
from __future__ import annotations

# Force UTF-8 for all file I/O before any other imports.
# PYTHONUTF8=1 only takes effect when set before Python starts (via launch.bat
# or the shell), but setting it here ensures subprocesses we spawn also inherit
# it. The io reconfigure calls fix stdin/stdout for the current process.
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pipeline import analyzer, downloader, exporter, frames, transcriber

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="视频摘要助手",
    page_icon="📺",
    layout="centered",
)

st.title("📺 视频摘要助手")
st.caption("为父母生成简体中文视频摘要 · 支持 YouTube 链接")

# ---------------------------------------------------------------------------
# Result dataclass (stored in session_state to survive Streamlit reruns)
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    title: str
    summary: str
    pdf_bytes: bytes


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_pipeline(url: str, tmp_dir: str, status) -> PipelineResult:
    status.update(label="⬇️ 正在下载视频与字幕…")
    dl = downloader.run(url, tmp_dir)

    transcript: str
    if dl.transcript:
        transcript = dl.transcript
        status.update(label="✅ 已找到字幕，跳过语音识别")
    else:
        status.update(label="🎙️ 正在识别音频（Whisper）…")
        if dl.audio_path is None:
            raise RuntimeError("音频文件未找到，无法进行语音识别。")
        transcript = transcriber.run(dl.audio_path)

    status.update(label="🖼️ 正在提取关键帧…")
    frame_paths = frames.extract(dl.video_path, tmp_dir)

    status.update(label="🔍 正在分析视频内容（Claude）…")
    content_description = analyzer.describe(transcript, frame_paths, title=dl.title)

    status.update(label="✍️ 正在生成中文摘要…")
    chinese_summary = analyzer.summarize(content_description, title=dl.title)

    status.update(label="📄 正在生成 PDF…")
    pdf_bytes = exporter.to_pdf(chinese_summary, title=dl.title)

    return PipelineResult(
        title=dl.title,
        summary=chinese_summary,
        pdf_bytes=pdf_bytes,
    )


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

url_input = st.text_input(
    "YouTube 链接",
    placeholder="https://www.youtube.com/watch?v=...",
    help="支持所有公开 YouTube 视频",
)

start = st.button("🚀 开始处理", type="primary", disabled=not url_input.strip())

if start and url_input.strip():
    # Clear previous result on new run
    st.session_state.pop("result", None)

    tmp_dir = tempfile.mkdtemp(prefix="tldw_")
    try:
        with st.status("正在处理视频，请稍候…", expanded=True) as status:
            result = run_pipeline(url_input.strip(), tmp_dir, status)
            status.update(label="✅ 处理完成！", state="complete", expanded=False)
        st.session_state["result"] = result
    except Exception as exc:
        st.error(f"处理失败：{exc}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# Display result (persists across reruns via session_state)
if "result" in st.session_state:
    result: PipelineResult = st.session_state["result"]

    st.divider()
    st.subheader(f"📝 {result.title}")
    st.markdown(result.summary)
    st.divider()

    # Safe filename: strip non-ASCII characters for download
    safe_filename = "摘要.pdf"
    st.download_button(
        label="📥 下载 PDF 摘要",
        data=result.pdf_bytes,
        file_name=safe_filename,
        mime="application/pdf",
        type="secondary",
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    "<br><br><div style='text-align:center; color: #888; font-size: 0.8em;'>"
    "由 Claude Sonnet + Whisper 驱动 · 专为父母设计</div>",
    unsafe_allow_html=True,
)
