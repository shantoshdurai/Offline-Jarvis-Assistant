@echo off
cd /d "%~dp0"
git add .
git commit -m "Update Jarvis Assistant"
git push origin master
pause
