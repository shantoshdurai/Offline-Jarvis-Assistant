@echo off
title Jarvis Setup
color 0A

echo ==============================================
echo Jarvis Assistant Setup
echo ==============================================

cd /d "%~dp0"

echo Activating Virtual Environment...
call venv\Scripts\activate.bat

echo Installing/Verifying Dependencies...
set PIP_DEFAULT_TIMEOUT=1000
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
pip install -r requirements.txt

if not exist "models\gemma-3-270m-it-Q4_K_M.gguf" (
    echo Downloading Gemma 3 Model...
    python -m pip install huggingface_hub
    hf download lmstudio-community/gemma-3-270m-it-GGUF gemma-3-270m-it-Q4_K_M.gguf --local-dir models
)

if not exist "%USERPROFILE%\.cache\huggingface\hub\models--Systran--faster-whisper-base.en" (
    echo.
    echo =======================================================
    echo Downloading Whisper Voice Recognition Model...
    echo =======================================================
    hf download Systran/faster-whisper-base.en
)

echo.
echo ==============================================
echo Setup Complete! You can now run jarvis.bat
echo ==============================================
pause
