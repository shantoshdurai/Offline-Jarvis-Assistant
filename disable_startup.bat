@echo off
title Disable Jarvis Auto-Start
color 0C
cd /d "%~dp0"

echo ============================================================
echo   Disabling Jarvis Fast Agent Windows Auto-Start
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$StartupPath = \"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\JarvisFastAgent.lnk\"; ^
   if (Test-Path $StartupPath) { ^
       Remove-Item $StartupPath; ^
       Write-Host '[OK] Jarvis removed from Windows Startup.' -ForegroundColor Yellow ^
   } else { ^
       Write-Host 'Jarvis was not present in Windows Startup.' ^
   }"

echo.
pause
