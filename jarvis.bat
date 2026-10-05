@echo off
title Jarvis AI Assistant
color 0B
cd /d "%~dp0"
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
call venv\Scripts\activate.bat
python gui.py
