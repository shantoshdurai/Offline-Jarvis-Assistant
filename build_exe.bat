@echo off
title Building Jarvis GUI...
color 0B
cd /d "%~dp0"
echo Activating Virtual Environment...
call venv\Scripts\activate.bat

echo Cleaning old build...
rmdir /s /q build
rmdir /s /q dist

echo Compiling Application with PyInstaller...
echo This might take a couple of minutes depending on your CPU.
pyinstaller --noconfirm --onedir --windowed --name "Jarvis" ^
  --hidden-import pyttsx3.drivers.sapi5 ^
  --collect-all llama_cpp ^
  --collect-all faster_whisper ^
  --collect-all openwakeword ^
  --add-data "venv\Lib\site-packages\customtkinter;customtkinter/" ^
  gui.py

echo.
echo Copying Local AI Models to Application Folder...
xcopy models dist\Jarvis\models\ /E /H /C /I

echo.
echo ==============================================
echo Build Complete! 
echo Your Standalone Application is located at:
echo C:\Users\Dog\Downloads\Gemma3-Assistant\dist\Jarvis\Jarvis.exe
echo ==============================================
