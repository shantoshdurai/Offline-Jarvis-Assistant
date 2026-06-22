# Local Jarvis AI Assistant

A 100% offline, highly responsive AI assistant built in Python. It runs entirely on your local CPU with zero internet required.

## Features
- **100% Offline**: Completely private, no data leaves your machine.
- **Continuous Conversation**: A dynamic interaction loop that listens and responds naturally.
- **Local AI Brain**: Powered by GGUF quantization via `llama.cpp` for CPU inference.
- **Wake Word**: Detects "Hey Jarvis" instantly using `openwakeword`.
- **Native TTS**: Synthesizes high-speed offline responses via Windows native `SpeechSynthesizer`.
- **Sleek GUI**: Modern graphical interface built with `customtkinter`.

## Getting Started

### 1. Setup
Run the `setup.bat` file to automatically create a virtual environment, install all required pip packages, and download the Whisper and Wake Word models.

### 2. Add an LLM
This project requires a localized AI model in `.gguf` format. 
Download your preferred lightweight model (e.g., Llama 3.2 3B or Gemma 3) and place the `.gguf` file into the `/models` directory. Update the model path in `gui.py`.

### 3. Run
Double click `jarvis.bat` to launch the assistant, or run `build_exe.bat` to compile the entire project into a portable, standalone Desktop Application!
