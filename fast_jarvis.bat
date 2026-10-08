@echo off
title Jarvis AI Fast Agent (DeepSeek 4.1 Flash + Parakeet-EOU)
color 0B
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" fast_agent.py %*
) else (
    python fast_agent.py %*
)

if not "%1"=="--minimized" pause
