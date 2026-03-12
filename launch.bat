@echo off
cd /d "%~dp0"
title 视频摘要助手

:: Force UTF-8 for all Python I/O (prevents charmap errors with Chinese text)
set PYTHONUTF8=1

:: Download fonts if missing
python scripts\download_fonts.py

:: Start the app — Streamlit opens the browser automatically
python -m streamlit run app.py --browser.gatherUsageStats false

:: If Streamlit exits, pause so the user can read any error message
if %errorlevel% neq 0 (
    echo.
    echo 启动失败，请检查上方错误信息。
    pause
)
