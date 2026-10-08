# Offline & Fast Jarvis AI Assistant

A high-performance AI assistant and developer copilot for Windows, supporting both **100% Offline Local Operation** and a **Lightning-Fast Hybrid Engine** powered by NVIDIA Parakeet-EOU INT8 speech recognition and DeepSeek 4.1 Flash.

---

## ⚡ Fast Agent Mode (New)

The Fast Agent is engineered for instant responsiveness with minimal latency and smart fallbacks:

- **OpenWhispr-Style Silent Background Operation**:
  - **1st Launch**: Starts silently into the Windows system tray with a custom blue pill icon (zero intrusive terminal windows).
  - **Floating Voice Pill**: Pressing `Ctrl+Shift+Space` (or saying `"Hey Jarvis"`) pops up the transparent floating pill overlay with dancing waveform equalizer bars and exact OpenWhispr harmonic chimes (C5 $\rightarrow$ E5 start, D5 $\rightarrow$ A4 stop). Tucks away automatically when done.
  - **2nd Launch / Windows Search**: Searching "Jarvis" in Windows Search or clicking the tray icon instantly brings up the sleek dark modern dashboard GUI (activity feed, chat, quick actions, settings).
  - **Single-Instance IPC (Port 49155)**: Automatically prevents multiple running instances and routes launch events to the active assistant.
  - **Clean 1-Click Shutdown**: Click "Stop Jarvis" in the dashboard or tray to terminate completely and release all mic/hardware resources.
- **Sub-50ms Speech Recognition**: Powered by NVIDIA's `Parakeet-EOU-120M` INT8 ONNX streaming model with instant End-of-Utterance (`<EOU>`) boundary detection. Falls back automatically to `faster-whisper`.
- **DeepSeek 4.1 Flash**: Ultra-fast, low-cost intelligence via OpenRouter with automatic zero-cost fallback to `openrouter/free` if limits or network issues occur.
- **Direct YouTube Video Player**: Queries YouTube and directly launches and plays the top matching video (instead of just opening search result pages).
- **Modality-Aware Pipeline**: Distinguishes `[Voice Input]` from `[Typed Input]` so Jarvis always knows whether you spoke into your mic or typed into the dashboard.
- **Push-to-Talk & Wake Word**:
  - Global Hotkeys: `Ctrl+Shift+Space`, `Ctrl+Alt+J`, and `Ctrl+Win`.
  - Background Wake Word: Always-listening `"Hey Jarvis"` via OpenWakeWord.
- **Dynamic Mic Calibration**: Automatically measures your microphone's ambient noise floor on startup to prevent stuck voice detection on laptop mic arrays.
- **Dual Voice Engine**: High-fidelity Edge-TTS neural speech (`en-GB-RyanNeural`) with instant offline Windows SAPI (`pyttsx3`) fallback if Microsoft servers or DNS are unavailable.

### Quick Start (Fast Agent)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Key**:
   Copy `.env.example` to `.env` and insert your OpenRouter API key:
   ```env
   OPENROUTER_API_KEY=sk-or-v1-...
   OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash
   FALLBACK_MODEL=openrouter/free
   ```

3. **Download Parakeet STT Model** (~112 MB):
   ```bash
   python download_parakeet.py
   ```

4. **Launch**:
   - Double-click `fast_jarvis.bat` or press the Windows Start key, type **Jarvis**, and hit Enter.
   - It will run quietly in the system tray.
   - Searching **Jarvis** a second time brings up the modern dashboard.
   - To launch with an interactive console for debugging, run: `fast_jarvis.bat --console`.

5. **Auto-Start on Boot & Shortcut Keys**:
   - Double-click `enable_startup.bat` to have Jarvis launch silently into the system tray on every Windows boot.
   - **Global Shortcuts (Active 24/7 anywhere in Windows)**:
     - `Ctrl + Shift + Space` / `Ctrl + Alt + J` / `Ctrl + Win` : Push-to-talk voice command.
     - `Ctrl + Alt + H` : Show or hide debug console window.
     - `"Hey Jarvis"` : Hands-free wake word.
     - System Tray Icon : Double-click to open Dashboard, right-click to trigger voice or stop Jarvis.
   - To disable auto-start, double-click `disable_startup.bat`.

---

## 🛡️ 100% Offline Local Mode

Runs completely offline on your hardware with zero internet required:

- **GPU Acceleration**: CUDA offload to NVIDIA GPUs via `llama-cpp-python` and CUDA-accelerated `faster-whisper`.
- **Live Hardware Telemetry Sidebar**: Real-time display of Tokens Per Second (TPS), response latency, GPU VRAM usage, GPU core utilization %, System RAM, CPU %, and live mic bounce meter.
- **Built-in System & Browser Tools**:
  - Direct YouTube playback, LeetCode daily challenge solver via GraphQL, and web search.
  - Launch applications (VS Code, Firefox, Chrome, Notepad, Terminal, Calculator, Blender, Godot).
  - Screen OCR, desktop screenshot capture, and local file search/viewing.
  - Hardware controls: volume up/down/mute and screen brightness.
- **CustomTkinter GUI & System Tray**: Runs quietly in the notification tray with 0ms instant cutoffs on Stop.

### Quick Start (Offline Mode)

1. Run `setup.bat` to create the virtual environment and install dependencies.
2. Place your preferred GGUF model in the `models/` directory (e.g. `qwen2.5-coder-3b-instruct-q4_k_m.gguf`).
3. Double-click `jarvis.bat` or run:
   ```powershell
   python fast_agent.py
   ```

---

## 🔧 Tools & Commands Supported

Jarvis executes actions natively across both modes:
- **YouTube Playback**: *"Play 10 hours Loki theme music on YouTube"* $\rightarrow$ directly opens the video URL.
- **Coding / LeetCode**: *"Open today's LeetCode daily problem"* $\rightarrow$ resolves today's question via GraphQL.
- **System Control**: *"Increase the volume"*, *"Mute"*, *"Set brightness to 80%"*, *"Lock screen"*.
- **Application Launch**: *"Open VS Code"*, *"Open Firefox"*, *"Open Terminal"*.
- **Local File System**: *"List files in Downloads"*, *"Search for file requirements.txt"*, *"Read file tools.py"*.
- **Screen & Vision**: *"Take a screenshot"*, *"Read what is on my screen"*.
