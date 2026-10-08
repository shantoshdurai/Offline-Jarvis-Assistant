@echo off
title Enable Jarvis Auto-Start
color 0A
cd /d "%~dp0"

echo ============================================================
echo   Enabling Jarvis Fast Agent Windows Auto-Start
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_autostart.ps1" -Action enable

echo.
echo ============================================================
echo   Done! Jarvis will now start automatically whenever you boot up.
echo.
echo   Shortcut Keys (Always active 24/7):
echo     * Ctrl + Shift + Space : Push-to-talk voice command
echo     * Ctrl + Alt + J       : Voice command hotkey / launch
echo     * Ctrl + Alt + H       : Show / Hide console window
echo     * "Hey Jarvis"         : Hands-free wake word
echo ============================================================
echo.
pause
