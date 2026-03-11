"""
Two-stage LLM analysis via OpenRouter (OpenAI-compatible API):
  1. describe()  — transcript + keyframes → structured English content description
  2. summarize() — content description → simplified Chinese markdown summary

Usage (standalone test):
    python -m pipeline.analyzer <transcript_file> <frames_dir>
"""
from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path

import openai
from PIL import Image

# OpenRouter model ID — change to any vision-capable model on openrouter.ai/models
_MODEL = "openai/gpt-4o-mini"
_MAX_IMAGE_PX = 1024
_JPEG_QUALITY = 85


def _client() -> openai.OpenAI:
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def describe(transcript: str, frame_paths: list[Path], title: str = "") -> str:
    """Return an English content description of the video."""
    system = (
        "You are a video content analyst. Your job is to produce a thorough, "
        "factual description of a video's content based on its transcript and "
        "visual keyframes.\n\n"
        "Focus on:\n"
        "- The main topic and purpose of the video\n"
        "- Key arguments, steps, or demonstrations presented\n"
        "- Important information visible in slides, charts, or on-screen text\n"
        "- The conclusion or main takeaway\n\n"
        "Rules:\n"
        "- Be specific and concrete; avoid vague generalizations\n"
        "- Do not editorialize or add opinions\n"
        "- If the transcript is in a language other than English, still write "
        "your output in English\n"
        "- Output should be 300-600 words"
    )

    n = len(frame_paths)
    header = (
        f"Analyze this YouTube video and produce a structured content description.\n\n"
        f"Video title: {title or 'Unknown'}\n\n"
        f"## Transcript\n{transcript}\n\n"
        f"## Visual Keyframes\n"
        f"The following {n} image{'s were' if n != 1 else ' was'} captured at "
        "scene-change points throughout the video. "
        "Review them for important visual information (slides, diagrams, "
        "on-screen text, demonstrations).\n\n"
        "Please structure your response as:\n"
        "1. TOPIC: What this video is about (2-3 sentences)\n"
        "2. KEY POINTS: The main things covered (bullet list, 5-10 items, be specific)\n"
        "3. VISUALS: Notable things seen in the keyframes worth mentioning\n"
        "4. CONCLUSION: The main takeaway or call to action"
    )

    # OpenAI-style content: text block followed by image_url blocks
    user_content: list[dict] = [{"type": "text", "text": header}]
    for path in frame_paths:
        b64 = _encode_frame(path)
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    response = _client().chat.completions.create(
        model=_MODEL,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content


def summarize(content_description: str, title: str = "") -> str:
    """Return a simplified Chinese markdown summary (300-500 chars)."""
    system = (
        "你是一位专门为非技术背景的中国父母撰写视频摘要的作者。\n\n"
        "你的读者特点：\n"
        "- 不会观看长视频，需要快速了解内容要点\n"
        "- 没有专业技术背景\n"
        "- 使用简体中文\n\n"
        "写作要求：\n"
        "- 语言：简体中文\n"
        "- 语气：亲切、自然，像朋友聊天一样，避免学术或技术腔调\n"
        "- 如遇到英文专业术语，用中文解释或在括号内标注\n"
        "- 格式必须完全按照用户要求的结构输出\n"
        "- 总字数控制在300-500个汉字之间"
    )

    user = (
        "请根据以下视频内容描述，为中国父母撰写一份简体中文摘要。\n\n"
        f"视频标题：{title or '未知标题'}\n\n"
        f"内容描述（英文）：\n{content_description}\n\n"
        "请严格按照以下格式输出，不要添加其他内容：\n\n"
        "**视频主旨**\n"
        "[用1-2句话说明这个视频讲的是什么，为什么值得关注]\n\n"
        "**主要内容**\n"
        "• [第一个要点，具体说明]\n"
        "• [第二个要点，具体说明]\n"
        "• [第三个要点，具体说明]\n"
        "• [根据内容可以有更多要点]\n\n"
        "**总结**\n"
        "[1-2句结语：这个视频对父母来说是否值得关注，或者可以从中学到什么]"
    )

    response = _client().chat.completions.create(
        model=_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _encode_frame(path: Path) -> str:
    """Load a JPEG, resize to max _MAX_IMAGE_PX on longest side, return base64."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((_MAX_IMAGE_PX, _MAX_IMAGE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    img.close()
    return base64.standard_b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m pipeline.analyzer <transcript_file> <frames_dir>")
        sys.exit(1)
    from dotenv import load_dotenv
    load_dotenv()

    transcript_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    frames_dir = Path(sys.argv[2])
    frame_list = sorted(frames_dir.glob("*.jpg"))[:30]

    print(f"Running describe() with {len(frame_list)} frames...")
    description = describe(transcript_text, frame_list, title="Test Video")
    print("\n--- Content Description ---")
    print(description)

    print("\nRunning summarize()...")
    summary = summarize(description, title="Test Video")
    print("\n--- Chinese Summary ---")
    print(summary)
