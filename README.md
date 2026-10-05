# Local Jarvis AI Assistant & DSA Coding Mentor

A 100% offline, highly responsive AI assistant and DSA mentor built in Python. Runs completely locally on your hardware with zero internet required.

## Key Features
- **100% Offline & Private**: Zero data leaves your machine; runs completely on local hardware.
- **GPU Acceleration**: Full CUDA offload to NVIDIA GeForce RTX (tested on RTX 2050 with ~43 tokens/sec) via `llama-cpp-python` and CUDA-accelerated `faster-whisper`.
- **Live Hardware Telemetry Sidebar**: Real-time display of Tokens Per Second (TPS), response latency, GPU VRAM usage, GPU core utilization %, System RAM, CPU %, and a live microphone volume bounce meter.
- **Built-in System & Browser Tools**:
  - Open YouTube, LeetCode problems, and web searches in Firefox, Chrome, or default browser.
  - Launch applications (VS Code, Notepad, Terminal, PowerShell, Calculator, Explorer).
  - Take desktop screenshots and save directly to your Pictures folder.
- **Instant Speech Control & Stop**: Native Windows SAPI voice with 0ms instant cutoffs on Stop.
- **System Tray Integration**: Runs quietly in the Windows notification tray with options to restore, stop, or terminate completely with zero lingering background processes.
- **Wake Word**: Fast, low-resource "Hey Jarvis" wake word detection via `openwakeword`.

## Getting Started

### 1. Setup
Run `setup.bat` to automatically create a virtual environment, install dependencies, and download the default models.

### 2. Add an LLM
Place your preferred GGUF model in the `models/` directory (e.g., `qwen2.5-coder-3b-instruct-q4_k_m.gguf` or `gemma-3-270m-it-Q4_K_M.gguf`). Jarvis automatically prioritizes the best coder / Qwen model available.

### 3. Run
Double-click `jarvis.bat` or `start_jarvis.bat` to launch the assistant, or run:
```powershell
.\venv\Scripts\python.exe gui.py
```
To compile into a standalone desktop executable, run `build_exe.bat`.
