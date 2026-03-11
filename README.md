# 视频摘要助手 · tldw4chineseparents

Paste a YouTube link → get a simplified Chinese summary as a PDF.

Built for sharing long videos with parents who won't watch them.

---

## What it does

1. Downloads the YouTube video and extracts captions (or transcribes audio via Whisper if none exist)
2. Captures keyframes at scene changes
3. Sends transcript + frames to an LLM to produce a content description
4. Distills that into a concise, readable **simplified Chinese summary**
5. Exports the result as a **PDF** you can send directly

---

## Prerequisites

Install these before anything else.

### 1. Python 3.11+

Download from https://www.python.org/downloads/

> During installation on Windows, check **"Add Python to PATH"**.

Verify in a terminal:
```
python --version
```

### 2. ffmpeg

Download the full build from https://www.gyan.dev/ffmpeg/builds/ → **ffmpeg-release-full.7z**

Extract it and add the `bin/` folder to your system PATH.

Verify:
```
ffmpeg -version
```

### 3. API keys

You need two API keys:

**OpenAI** (for audio transcription via Whisper)
- Sign up at https://platform.openai.com
- Go to **API keys** → Create new secret key
- Add a few dollars of credit under **Billing**

**OpenRouter** (for the LLM that writes the summary)
- Sign up at https://openrouter.ai
- Go to **Keys** → Create key
- Add credit under **Credits** (a few dollars goes a long way)

---

## Setup

Run these commands once in a terminal inside the project folder.

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API keys

Copy the example file:
```bash
cp .env.example .env
```

Open `.env` and fill in your keys:
```
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
```

> `.env` is gitignored and never committed.

### 3. Download fonts

The PDF export needs a Chinese font. Run once:
```bash
python scripts/download_fonts.py
```

This downloads ~22 MB of Noto Sans SC fonts into `assets/`. The launcher also runs this automatically on startup.

---

## Running the app

**Double-click `launch.bat`** — the browser opens automatically.

Or from a terminal:
```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Paste a YouTube URL, click **开始处理**, wait a minute or two, then download the PDF.

---

## Running with Docker

If you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed:

```bash
# Build and start
docker compose up --build

# Open http://localhost:8501 in your browser

# Stop
docker compose down
```

Docker handles all dependencies including ffmpeg and fonts — no manual setup needed beyond having Docker Desktop and a `.env` file.

---

## Changing the LLM model

The default model is `openai/gpt-4o-mini` via OpenRouter. To use a different model, edit line 21 of [`pipeline/analyzer.py`](pipeline/analyzer.py):

```python
_MODEL = "openai/gpt-4o-mini"
```

Any vision-capable model on https://openrouter.ai/models works. Good alternatives:
- `anthropic/claude-sonnet-4-5` — higher quality, higher cost
- `google/gemini-flash-1.5` — fast and cheap
- `openai/gpt-4o` — strong vision, moderate cost

---

## Project structure

```
tldw4chineseparents/
├── app.py                   # Streamlit UI
├── launch.bat               # Windows double-click launcher
├── pipeline/
│   ├── downloader.py        # YouTube download + caption extraction
│   ├── transcriber.py       # OpenAI Whisper transcription
│   ├── frames.py            # ffmpeg keyframe extraction
│   ├── analyzer.py          # LLM content description + Chinese summary
│   └── exporter.py          # PDF generation (fpdf2 + CJK fonts)
├── scripts/
│   └── download_fonts.py    # One-time font download
├── assets/                  # NotoSansSC fonts (downloaded, not committed)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                     # Your API keys (never commit this)
```

---

## Troubleshooting

**"正在识别音频" takes a long time**
The video has no auto-captions so the full audio is being transcribed via Whisper. This is normal for videos without captions — a 1-hour video may take 2–3 minutes.

**PDF download button appears but file is blank / garbled**
The font files in `assets/` may be corrupted. Delete them and re-run `python scripts/download_fonts.py`.

**"Not enough horizontal space" error**
This was a known bug that has been fixed. Make sure you have the latest version of `pipeline/exporter.py`.

**ffmpeg not found**
Make sure the ffmpeg `bin/` folder is on your PATH. Open a new terminal after adding it — PATH changes don't apply to already-open windows.

**429 Too Many Requests from YouTube**
YouTube rate-limits subtitle downloads. The app automatically falls back to Whisper transcription when this happens, so the summary will still be generated — just slightly slower.
