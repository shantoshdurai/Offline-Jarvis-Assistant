@echo off
title Jarvis AI Fast Agent (DeepSeek 4.1 Flash + Parakeet-EOU)
color 0B
cd /d "%~dp0"

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python fast_agent.py
pause
