import os
import time
import threading
import queue
import re
import numpy as np
import pyaudio
import wave
import customtkinter as ctk
import subprocess
import sys
import site
import win32com.client
import pythoncom
import psutil
from PIL import Image, ImageDraw
import pystray
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

# Ensure CUDA dlls (cublas, cudnn) can be loaded for GPU-accelerated Whisper and llama-cpp
for s in site.getsitepackages() + [r"C:\Users\Dog\AppData\Local\Programs\Python\Python311\Lib\site-packages"]:
    candidate = os.path.join(s, "torch", "lib")
    if os.path.exists(candidate) and candidate not in os.environ.get("PATH", ""):
        os.environ["PATH"] = candidate + os.pathsep + os.environ["PATH"]
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(candidate)
            except Exception:
                pass

import ctranslate2
from llama_cpp import Llama
from faster_whisper import WhisperModel
from openwakeword.model import Model
import tools

# Initialize NVML for fast, real-time GPU telemetry
HAS_NVML = False
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVML = True
except Exception:
    try:
        import nvidia_ml_py as pynvml
        pynvml.nvmlInit()
        HAS_NVML = True
    except Exception:
        HAS_NVML = False

# Prevent crashes in PyInstaller Windowed mode when background libraries try to print
class DummyFile:
    def write(self, x): pass
    def flush(self): pass
if getattr(sys, 'frozen', False):
    sys.stdout = DummyFile()
    sys.stderr = DummyFile()

# --- CONFIGURATION ---
SYSTEM_PROMPT = """You are Jarvis, an offline personal AI assistant, system copilot, and DSA coding mentor running 100% locally on Shantosh's laptop.
You are powered by Qwen 2.5 Coder. You are NOT developed by OpenAI, NOT GPT-4, and NOT Gemini. Always identify yourself as Jarvis.
You have direct local access to Shantosh's Windows computer: files, desktop, installed games, display brightness, volume, and terminal CLI.

VOICE & RESPONSE STYLE:
- Your words are spoken aloud through text-to-speech. Never speak raw programming syntax, punctuation, or code lines.
- When explaining an algorithm or concept, explain the intuition simply in 2-3 sentences.
- Place actual code implementation cleanly in ```python ... ``` blocks.
- Be an interactive pair programmer: offer hints, ask if the user wants the problem opened on LeetCode, or ask if they want to try it first.

AVAILABLE TOOLS & HARDWARE CONTROLS:
You have real tools to control the computer. When asked to perform an action, use the exact format on its own line:
- Screen Vision / OCR: <<TOOL: inspect_screen()>>
- Check Installed Games: <<TOOL: get_installed_games()>>
- Adjust Brightness: <<TOOL: adjust_brightness("increase")>> (or "decrease", "set", 80)
- Adjust Volume: <<TOOL: adjust_volume("increase")>> (or "decrease", "mute")
- Open website: <<TOOL: open_url("https://youtube.com", browser="firefox")>>
- Open LeetCode: <<TOOL: open_leetcode("two-sum")>>
- Open application: <<TOOL: open_app("firefox")>> (or "code", "notepad", "terminal", "chrome", "calc")
- Take screenshot: <<TOOL: take_screenshot()>>
- Open folder: <<TOOL: open_folder("Downloads")>>
- Run terminal command: <<TOOL: run_command("command")>>
Always briefly tell the user what you are doing."""

HISTORY = [{"role": "system", "content": SYSTEM_PROMPT}]
is_processing = threading.Event()
voice_command_queue = queue.Queue()

class JarvisGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Jarvis AI Assistant — System Copilot & DSA Mentor")
        self.geometry("1180x740")
        self.minsize(980, 620)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.stop_event = threading.Event()
        self.is_speaking_lock = threading.Event()
        self.tts_queue = queue.Queue()
        self.sapi_voice = None
        self.tray_icon = None
        self.gpu_device_name = "Detecting GPU..."
        self.active_model_name = "Loading..."
        self._is_closed = False
        self.is_followup_turn = False
        
        # Thread-safe UI Dispatcher
        self.ui_queue = queue.Queue()
        self.check_ui_queue()
        
        # Handle clean window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # --- UI GRID LAYOUT ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        
        # --- LEFT PANEL: CHAT & INPUT ---
        self.chat_box = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 14), wrap="word")
        self.chat_box.grid(row=0, column=0, padx=(20, 10), pady=(20, 10), sticky="nsew")
        
        self.status_label = ctk.CTkLabel(self, text="Status: Booting AI Models...", text_color="yellow", font=("Arial", 16, "bold"))
        self.status_label.grid(row=1, column=0, pady=(0, 10))
        
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=(20, 10), pady=(0, 20), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type a message or say 'Hey Jarvis'...", font=("Arial", 14))
        self.entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.entry.bind("<Return>", self.send_text)
        
        self.send_btn = ctk.CTkButton(self.input_frame, text="Send", command=self.send_text, width=70)
        self.send_btn.grid(row=0, column=1, padx=(0, 5))

        self.speak_btn = ctk.CTkButton(self.input_frame, text="🎤 Speak", command=self.trigger_voice, width=80, fg_color="#27ae60", hover_color="#1e8449")
        self.speak_btn.grid(row=0, column=2, padx=(0, 5))

        self.stop_btn = ctk.CTkButton(self.input_frame, text="Stop", command=self.stop_action, width=70, fg_color="#c0392b", hover_color="#962d22")
        self.stop_btn.grid(row=0, column=3)

        # --- RIGHT PANEL: PERFORMANCE & TELEMETRY SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, width=310, corner_radius=12, fg_color="#181a20")
        self.sidebar.grid(row=0, column=1, rowspan=3, padx=(10, 20), pady=20, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Header
        sb_header = ctk.CTkLabel(self.sidebar, text="⚡ SYSTEM TELEMETRY", font=("Consolas", 15, "bold"), text_color="#00d2d3")
        sb_header.pack(pady=(12, 6), padx=14, anchor="w")

        # 1. Engine & Acceleration Card
        self.engine_card = ctk.CTkFrame(self.sidebar, fg_color="#22252e", corner_radius=8)
        self.engine_card.pack(fill="x", padx=12, pady=3)
        
        ctk.CTkLabel(self.engine_card, text="AI ACCELERATION & MODEL", font=("Arial", 9, "bold"), text_color="#8395a7").pack(anchor="w", padx=10, pady=(5, 1))
        
        self.lbl_model = ctk.CTkLabel(self.engine_card, text="Model: Qwen 2.5 Coder 3B", font=("Arial", 11, "bold"), text_color="#ffffff")
        self.lbl_model.pack(anchor="w", padx=10, pady=1)

        self.lbl_device = ctk.CTkLabel(self.engine_card, text="Device: NVIDIA RTX 2050 (CUDA)", font=("Arial", 11, "bold"), text_color="#2ecc71")
        self.lbl_device.pack(anchor="w", padx=10, pady=1)

        self.lbl_stt = ctk.CTkLabel(self.engine_card, text="STT: Whisper small.en (CUDA)", font=("Arial", 10), text_color="#bdc3c7")
        self.lbl_stt.pack(anchor="w", padx=10, pady=(1, 5))

        # 2. Real-Time Generation Speed Card (Live TPS & Latency)
        self.gen_card = ctk.CTkFrame(self.sidebar, fg_color="#22252e", corner_radius=8)
        self.gen_card.pack(fill="x", padx=12, pady=3)

        ctk.CTkLabel(self.gen_card, text="LIVE GENERATION PERFORMANCE", font=("Arial", 9, "bold"), text_color="#8395a7").pack(anchor="w", padx=10, pady=(5, 1))

        self.lbl_tps_val = ctk.CTkLabel(self.gen_card, text="0.0 TPS", font=("Consolas", 22, "bold"), text_color="#00d2d3")
        self.lbl_tps_val.pack(anchor="w", padx=10, pady=(0, 1))

        self.lbl_latency = ctk.CTkLabel(self.gen_card, text="Ready (0 tokens)", font=("Arial", 10), text_color="#bdc3c7")
        self.lbl_latency.pack(anchor="w", padx=10, pady=(0, 2))

        # STT Latency & Speedup
        self.lbl_stt_speed = ctk.CTkLabel(self.gen_card, text="STT Speed: Ready", font=("Arial", 10), text_color="#bdc3c7")
        self.lbl_stt_speed.pack(anchor="w", padx=10, pady=(0, 5))

        # 3. Hardware Resource Utilization Card (GPU VRAM, GPU %, RAM, CPU)
        self.hw_card = ctk.CTkFrame(self.sidebar, fg_color="#22252e", corner_radius=8)
        self.hw_card.pack(fill="x", padx=12, pady=3)

        ctk.CTkLabel(self.hw_card, text="HARDWARE METRICS (LIVE)", font=("Arial", 9, "bold"), text_color="#8395a7").pack(anchor="w", padx=10, pady=(5, 3))

        # VRAM
        self.lbl_vram = ctk.CTkLabel(self.hw_card, text="GPU VRAM: 0.00 / 4.00 GB (0%)", font=("Arial", 10), text_color="#ecf0f1")
        self.lbl_vram.pack(anchor="w", padx=10, pady=1)
        self.prog_vram = ctk.CTkProgressBar(self.hw_card, height=6, progress_color="#3498db")
        self.prog_vram.pack(fill="x", padx=10, pady=(1, 3))
        self.prog_vram.set(0.0)

        # GPU Util
        self.lbl_gpu_util = ctk.CTkLabel(self.hw_card, text="GPU Core Util: 0%", font=("Arial", 10), text_color="#ecf0f1")
        self.lbl_gpu_util.pack(anchor="w", padx=10, pady=1)

        # System RAM
        self.lbl_ram = ctk.CTkLabel(self.hw_card, text="System RAM: 0.0 / 0.0 GB (0%)", font=("Arial", 10), text_color="#ecf0f1")
        self.lbl_ram.pack(anchor="w", padx=10, pady=1)
        self.prog_ram = ctk.CTkProgressBar(self.hw_card, height=6, progress_color="#9b59b6")
        self.prog_ram.pack(fill="x", padx=10, pady=(1, 3))
        self.prog_ram.set(0.0)

        # CPU
        self.lbl_cpu = ctk.CTkLabel(self.hw_card, text="CPU Usage: 0%", font=("Arial", 10), text_color="#ecf0f1")
        self.lbl_cpu.pack(anchor="w", padx=10, pady=(1, 5))

        # 4. Mode & Microphone Activity Card
        self.audio_card = ctk.CTkFrame(self.sidebar, fg_color="#22252e", corner_radius=8)
        self.audio_card.pack(fill="x", padx=12, pady=3)

        ctk.CTkLabel(self.audio_card, text="CONVERSATION & MIC", font=("Arial", 9, "bold"), text_color="#8395a7").pack(anchor="w", padx=10, pady=(5, 2))
        
        # Continuous / Side Agent Toggle Switch
        self.continuous_mode_var = ctk.BooleanVar(value=True)
        self.mode_switch = ctk.CTkSwitch(
            self.audio_card,
            text="Continuous / Side Agent Mode",
            variable=self.continuous_mode_var,
            font=("Arial", 10, "bold"),
            progress_color="#2ecc71"
        )
        self.mode_switch.pack(anchor="w", padx=10, pady=(2, 4))

        self.lbl_mic_status = ctk.CTkLabel(self.audio_card, text="Wake Word: Hey Jarvis (Ready)", font=("Arial", 10), text_color="#2ecc71")
        self.lbl_mic_status.pack(anchor="w", padx=10, pady=1)

        self.prog_mic = ctk.CTkProgressBar(self.audio_card, height=7, progress_color="#2ecc71")
        self.prog_mic.pack(fill="x", padx=10, pady=(2, 6))
        self.prog_mic.set(0.0)

        # Bottom System Tray notice & Complete Terminate Button
        self.lbl_tray_info = ctk.CTkLabel(self.sidebar, text="📌 Running in system tray (^)", font=("Arial", 9), text_color="#7f8c8d")
        self.lbl_tray_info.pack(pady=(4, 2))

        self.btn_quit_all = ctk.CTkButton(
            self.sidebar, text="⏻ Quit Jarvis Completely", 
            command=self.on_closing,
            fg_color="#c0392b", hover_color="#962d22",
            height=30, font=("Arial", 11, "bold")
        )
        self.btn_quit_all.pack(fill="x", padx=12, pady=(0, 10), side="bottom")

        # Models and Audio
        self.llm = None
        self.whisper_model = None
        self.owwModel = None
        self.audio = None
        self.mic_stream = None
        
        # Start Native System Tray Icon in background
        self.setup_tray()

        # Start TTS Worker Thread
        threading.Thread(target=self.tts_worker, daemon=True).start()
        
        # Start Loading Thread
        threading.Thread(target=self.load_models, daemon=True).start()

    def post_ui(self, fn, *args, **kwargs):
        """Thread-safe way for background threads to dispatch calls to the main thread."""
        self.ui_queue.put((fn, args, kwargs))

    def check_ui_queue(self):
        """Processes pending UI actions on the main thread."""
        while not self.ui_queue.empty():
            try:
                fn, args, kwargs = self.ui_queue.get_nowait()
                fn(*args, **kwargs)
            except Exception:
                pass
        if not self._is_closed:
            self.after(20, self.check_ui_queue)

    def setup_tray(self):
        """Initializes a Windows hidden system tray icon with full process termination support."""
        try:
            size = 64
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((4, 4, 60, 60), fill=(24, 26, 31, 255), outline=(0, 210, 211, 255), width=3)
            draw.ellipse((16, 16, 48, 48), fill=(0, 160, 230, 255), outline=(255, 255, 255, 220), width=2)
            draw.ellipse((26, 26, 38, 38), fill=(255, 255, 255, 255))
            
            menu = pystray.Menu(
                pystray.MenuItem("Jarvis AI Assistant", None, enabled=False),
                pystray.MenuItem("Show / Restore", self.restore_from_tray, default=True),
                pystray.MenuItem("Stop Current Action", lambda: self.post_ui(self.stop_action)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit Jarvis Completely", lambda: self.post_ui(self.on_closing))
            )
            self.tray_icon = pystray.Icon("jarvis_tray", img, "Jarvis AI Assistant", menu=menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print("Failed to initialize system tray:", e)

    def restore_from_tray(self, icon=None, item=None):
        self.post_ui(self._bring_to_front)

    def _bring_to_front(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.after(150, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def on_closing(self):
        """Clean shutdown: stops speech, closes tray icon, closes audio, and forcefully exits all threads."""
        self._is_closed = True
        self.stop_action()
        try:
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass
        try:
            if self.mic_stream:
                self.mic_stream.stop_stream()
                self.mic_stream.close()
            if self.audio:
                self.audio.terminate()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    def flush_mic_buffer(self):
        """Discards any lingering audio from the microphone stream to prevent echo."""
        try:
            if self.mic_stream and self.mic_stream.is_active():
                while self.mic_stream.get_read_available() > 0:
                    self.mic_stream.read(self.mic_stream.get_read_available(), exception_on_overflow=False)
        except Exception:
            pass

    def reset_to_listening(self):
        """Cleanly restores state back to listening for wake word."""
        self.is_followup_turn = False
        self.post_ui(self._set_status_impl, "Listening for 'Hey Jarvis'...", "lightgreen")
        self.post_ui(self._set_widget_attr, self.lbl_mic_status, "text", "Wake Word: Hey Jarvis (Ready)", "text_color", "#2ecc71")
        self.post_ui(self._update_mic_level_impl, 0.0)
        is_processing.clear()
        if hasattr(self, "owwModel") and self.owwModel:
            try:
                self.owwModel.reset()
            except Exception:
                pass

    def _set_widget_attr(self, widget, *args):
        try:
            kwargs = {}
            for i in range(0, len(args), 2):
                kwargs[args[i]] = args[i+1]
            widget.configure(**kwargs)
        except Exception:
            pass

    def stop_action(self):
        """Immediately halts AI generation, voice output, drains mic, and resets to listening."""
        self.stop_event.set()
        
        if hasattr(self, "sapi_voice") and self.sapi_voice:
            try:
                self.sapi_voice.Speak("", 2) # Flag 2 = SVSFPurgeBeforeSpeak
            except Exception:
                pass
            
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except Exception:
                break
                
        self.is_speaking_lock.clear()
        self.flush_mic_buffer()
        self.set_generation_metrics(0.0, 0.0, 0, "Stopped")
        self.reset_to_listening()

    def update_chat(self, sender, text, color="white"):
        self.post_ui(self._update_chat_impl, sender, text, color)

    def _update_chat_impl(self, sender, text, color="white"):
        try:
            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", f"[{sender}]\n{text}\n\n")
            self.chat_box.see("end")
            self.chat_box.configure(state="disabled")
        except Exception:
            pass

    def start_assistant_message(self):
        self.post_ui(self._start_assistant_message_impl)

    def _start_assistant_message_impl(self):
        try:
            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", "[Jarvis]\n")
            self.chat_box.see("end")
            self.chat_box.configure(state="disabled")
        except Exception:
            pass

    def append_chat_token(self, token):
        self.post_ui(self._append_chat_token_impl, token)

    def _append_chat_token_impl(self, token):
        try:
            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", token)
            self.chat_box.see("end")
            self.chat_box.configure(state="disabled")
        except Exception:
            pass

    def finish_assistant_message(self):
        self.post_ui(self._finish_assistant_message_impl)

    def _finish_assistant_message_impl(self):
        try:
            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", "\n\n")
            self.chat_box.see("end")
            self.chat_box.configure(state="disabled")
        except Exception:
            pass

    def set_status(self, text, color="white"):
        self.post_ui(self._set_status_impl, text, color)

    def _set_status_impl(self, text, color="white"):
        try:
            self.status_label.configure(text=f"Status: {text}", text_color=color)
        except Exception:
            pass

    def set_generation_metrics(self, tps, elapsed, token_count, state=""):
        self.post_ui(self._set_generation_metrics_impl, tps, elapsed, token_count, state)

    def _set_generation_metrics_impl(self, tps, elapsed, token_count, state=""):
        try:
            if state == "Generating...":
                self.lbl_tps_val.configure(text=f"{tps:.1f} TPS", text_color="#00d2d3")
                self.lbl_latency.configure(text=f"Streaming: {elapsed:.1f}s ({token_count} tok)")
            elif state == "Done":
                self.lbl_tps_val.configure(text=f"{tps:.1f} TPS", text_color="#2ecc71")
                self.lbl_latency.configure(text=f"Done in {elapsed:.2f}s ({token_count} tok)")
            elif state == "Stopped":
                self.lbl_tps_val.configure(text="0.0 TPS", text_color="#e74c3c")
                self.lbl_latency.configure(text="Generation stopped")
            else:
                self.lbl_tps_val.configure(text="0.0 TPS", text_color="#bdc3c7")
                self.lbl_latency.configure(text="Ready")
        except Exception:
            pass

    def set_stt_metrics(self, stt_latency, speedup):
        self.post_ui(self._set_stt_metrics_impl, stt_latency, speedup)

    def _set_stt_metrics_impl(self, stt_latency, speedup):
        try:
            self.lbl_stt_speed.configure(text=f"STT Speed: {stt_latency:.2f}s ({speedup:.1f}x real-time)")
        except Exception:
            pass

    def update_mic_level(self, volume):
        self.post_ui(self._update_mic_level_impl, volume)

    def _update_mic_level_impl(self, volume):
        try:
            val = min(1.0, max(0.0, volume / 1000.0))
            self.prog_mic.set(val)
        except Exception:
            pass

    def telemetry_worker(self):
        """Monitors system RAM, CPU, and NVIDIA GPU VRAM/Utilization every 1s."""
        gpu_handle = None
        if HAS_NVML:
            try:
                gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                gpu_handle = None

        while not self._is_closed:
            try:
                mem = psutil.virtual_memory()
                ram_used = mem.used / (1024**3)
                ram_total = mem.total / (1024**3)
                ram_pct = mem.percent
                cpu_pct = psutil.cpu_percent()

                vram_used = 0.0
                vram_total = 4.0
                vram_pct = 0
                gpu_util = 0

                if gpu_handle:
                    try:
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
                        vram_used = mem_info.used / (1024**3)
                        vram_total = mem_info.total / (1024**3)
                        vram_pct = int(mem_info.used / mem_info.total * 100)
                        rates = pynvml.nvmlDeviceGetUtilizationRates(gpu_handle)
                        gpu_util = rates.gpu
                    except Exception:
                        pass

                self.post_ui(self._update_resource_labels_impl,
                            ram_used, ram_total, ram_pct, cpu_pct,
                            vram_used, vram_total, vram_pct, gpu_util)
            except Exception:
                pass
            time.sleep(1.0)

    def _update_resource_labels_impl(self, ram_used, ram_total, ram_pct, cpu_pct, vram_used, vram_total, vram_pct, gpu_util):
        try:
            self.lbl_vram.configure(text=f"GPU VRAM: {vram_used:.2f} / {vram_total:.2f} GB ({vram_pct}%)")
            self.prog_vram.set(min(1.0, max(0.0, vram_pct / 100.0)))
            self.lbl_gpu_util.configure(text=f"GPU Core Util: {gpu_util}%")
            self.lbl_ram.configure(text=f"System RAM: {ram_used:.1f} / {ram_total:.1f} GB ({ram_pct}%)")
            self.prog_ram.set(min(1.0, max(0.0, ram_pct / 100.0)))
            self.lbl_cpu.configure(text=f"CPU Usage: {cpu_pct:.0f}%")
        except Exception:
            pass

    def clean_for_speech(self, text):
        """Prepares text for TTS: strips raw code blocks, tools, URLs, and markdown."""
        if not text:
            return ""
        t = re.sub(r'<<TOOL:.*?>>', '', text)
        t = re.sub(r'```[\s\S]*?```', ' I have placed the code implementation on your screen. ', t)
        if "```" in t:
            t = t.split("```")[0] + ' I have placed the code implementation on your screen. '
        t = re.sub(r'`([^`]+)`', r'\1', t)
        t = re.sub(r'#+\s*', '', t)
        t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
        t = re.sub(r'\*([^*]+)\*', r'\1', t)
        t = re.sub(r'[-*]\s+', '', t)
        t = re.sub(r'https?://\S+', '', t)
        t = t.replace("'", " ").replace('"', " ").replace(";", " ").replace("$", " ")
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def tts_worker(self):
        """Background worker that speaks queued sentences sequentially using native SAPI."""
        pythoncom.CoInitialize()
        try:
            self.sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
            self.sapi_voice.Rate = 1
        except Exception as e:
            print("Failed to initialize SAPI:", e)

        while not self._is_closed:
            text = self.tts_queue.get()
            if self.stop_event.is_set():
                continue
            clean_text = self.clean_for_speech(text)
            if not clean_text or len(clean_text) < 2:
                if self.tts_queue.empty() and not self.is_speaking_lock.is_set():
                    self.reset_to_listening()
                continue

            self.is_speaking_lock.set()
            self.set_status("Jarvis is speaking...", "orange")
            self.post_ui(self._set_widget_attr, self.lbl_mic_status, "text", "Audio: Speaking Aloud...", "text_color", "#e67e22")

            try:
                self.sapi_voice.Speak(clean_text, 1) # Flag 1 = SVSFlagsAsync
                while self.sapi_voice.Status.RunningState == 2:
                    if self.stop_event.is_set():
                        self.sapi_voice.Speak("", 2) # Flag 2 = SVSFPurgeBeforeSpeak
                        break
                    time.sleep(0.04)
            except Exception:
                pass

            if self.tts_queue.empty():
                time.sleep(0.4)
                self.flush_mic_buffer()
                self.is_speaking_lock.clear()
                
                # Continuous / Side Agent follow-up turn!
                if self.continuous_mode_var.get() and not self.stop_event.is_set():
                    self.is_followup_turn = True
                    self.set_status("Listening for follow-up... (Speak now)", "#00d2d3")
                    self.post_ui(self._set_widget_attr, self.lbl_mic_status, "text", "Mic: Listening for follow-up...", "text_color", "#00d2d3")
                    voice_command_queue.put(True)
                else:
                    self.reset_to_listening()

    def load_models(self):
        try:
            # Prioritize: 1) Q2_K (fastest 2-bit quantization, ~51.3 TPS), 2) Q4_K_M, 3) Coder
            model_path = "models/qwen2.5-coder-3b-instruct-q2_k.gguf"
            if os.path.exists("models"):
                candidates = [f for f in os.listdir("models") if f.endswith(".gguf")]
                if candidates:
                    candidates.sort(key=lambda f: (
                        "q2_k" in f.lower(),
                        "coder" in f.lower(),
                        "qwen" in f.lower(),
                        os.path.getsize(os.path.join("models", f))
                    ), reverse=True)
                    model_path = os.path.join("models", candidates[0])

            model_name = os.path.basename(model_path)
            self.active_model_name = model_name
            self.update_chat("System", f"Loading LLM on GPU ({model_name})...", "gray")
            
            # Offload all layers to NVIDIA RTX 2050 (4 GB VRAM)
            try:
                self.llm = Llama(
                    model_path=model_path,
                    n_gpu_layers=-1,
                    n_ctx=4096,
                    verbose=False
                )
                self.gpu_device_name = "NVIDIA RTX 2050 (CUDA)"
                self.post_ui(self._set_widget_attr, self.lbl_device, "text", "Device: NVIDIA RTX 2050 (CUDA)", "text_color", "#2ecc71")
                self.update_chat("System", "LLM successfully offloaded to NVIDIA RTX 2050 GPU!", "#2ecc71")
            except Exception as e:
                print("GPU load failed, falling back to CPU:", e)
                self.llm = Llama(
                    model_path=model_path,
                    n_gpu_layers=0,
                    n_ctx=4096,
                    verbose=False
                )
                self.gpu_device_name = "CPU Only (Fallback)"
                self.post_ui(self._set_widget_attr, self.lbl_device, "text", "Device: CPU Fallback", "text_color", "#e67e22")

            short_model_name = "Qwen 2.5 Coder (Q2_K 2-bit)" if "q2_k" in model_name.lower() else ("Qwen 2.5 Coder 3B" if "qwen" in model_name.lower() else model_name[:22])
            self.post_ui(self._set_widget_attr, self.lbl_model, "text", f"Model: {short_model_name}")

            self.update_chat("System", "Loading Whisper (Ears)...", "gray")
            whisper_device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            whisper_compute = "float16" if whisper_device == "cuda" else "int8"
            
            try:
                self.whisper_model = WhisperModel("small.en", device=whisper_device, compute_type=whisper_compute)
                self.update_chat("System", f"Loaded Whisper small.en on {whisper_device.upper()}.", "gray")
                self.post_ui(self._set_widget_attr, self.lbl_stt, "text", f"STT: Whisper small.en ({whisper_device.upper()})")
            except Exception:
                self.whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
                self.update_chat("System", "Loaded Whisper base.en on CPU.", "gray")
                self.post_ui(self._set_widget_attr, self.lbl_stt, "text", "STT: Whisper base.en (CPU)")
            
            self.update_chat("System", "Loading OpenWakeWord...", "gray")
            self.owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            
            self.update_chat("System", "All models loaded! Jarvis is online.", "green")
            self.reset_to_listening()
            
            # Start Audio and Telemetry loops
            self.start_audio()
            threading.Thread(target=self.telemetry_worker, daemon=True).start()
        except Exception as e:
            self.update_chat("Error", f"Failed to load models: {e}", "red")
            self.set_status("Error loading models", "red")

    def start_audio(self):
        self.CHUNK = 1280
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        
        self.audio = pyaudio.PyAudio()
        self.mic_stream = self.audio.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)
        
        threading.Thread(target=self.wake_word_listener, daemon=True).start()
        threading.Thread(target=self.process_queue, daemon=True).start()

    def wake_word_listener(self):
        counter = 0
        while not self._is_closed:
            try:
                if not is_processing.is_set() and not self.is_speaking_lock.is_set():
                    data = self.mic_stream.read(self.CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    counter += 1
                    if counter % 4 == 0:
                        vol = float(np.abs(audio_data).mean())
                        self.update_mic_level(vol)

                    prediction = self.owwModel.predict(audio_data)
                    max_score = max(prediction.values()) if prediction else 0.0
                    
                    if max_score > 0.18:
                        is_processing.set()
                        voice_command_queue.put(True)
                        self.owwModel.reset()
                else:
                    self.flush_mic_buffer()
                    time.sleep(0.05)
            except OSError:
                break
            except Exception:
                time.sleep(0.5)

    def trigger_voice(self):
        """Called when user clicks the 🎤 Speak button."""
        if not is_processing.is_set() and not self.is_speaking_lock.is_set():
            is_processing.set()
            voice_command_queue.put(True)

    def process_queue(self):
        while not self._is_closed:
            if not voice_command_queue.empty():
                voice_command_queue.get()
                self.handle_voice_interaction()
            time.sleep(0.05)

    def handle_voice_interaction(self):
        is_processing.set()
        
        if self.is_followup_turn:
            self.set_status("Listening for follow-up... (Speak now)", "#00d2d3")
            self.post_ui(self._set_widget_attr, self.lbl_mic_status, "text", "Mic: Listening for follow-up...", "text_color", "#00d2d3")
        else:
            self.set_status("Listening... Speak now!", "orange")
            self.post_ui(self._set_widget_attr, self.lbl_mic_status, "text", "Mic: Recording Voice...", "text_color", "#f39c12")
        
        frames = []
        silent_chunks = 0
        chunks_per_second = self.RATE / self.CHUNK
        max_silent_chunks = int(1.8 * chunks_per_second)
        max_total_chunks = int(20 * chunks_per_second)
        timeout_chunks = int(5.5 * chunks_per_second)
        talking_started = False
        
        self.flush_mic_buffer()
        SPEECH_THRESHOLD = 260 # Calibrated for laptop Realtek mic array
            
        for i in range(max_total_chunks):
            if self.stop_event.is_set() or self._is_closed:
                break
            data = self.mic_stream.read(self.CHUNK, exception_on_overflow=False)
            frames.append(data)
            
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = float(np.abs(audio_data).mean())
            self.update_mic_level(volume)
            
            if volume > SPEECH_THRESHOLD: 
                talking_started = True
                silent_chunks = 0
            elif talking_started:
                silent_chunks += 1
                
            if talking_started and silent_chunks > max_silent_chunks:
                break
            if not talking_started and i > timeout_chunks:
                break
                
        self.update_mic_level(0.0)

        if self.stop_event.is_set() or self._is_closed:
            self.reset_to_listening()
            return

        # Crucial: If user never actually started speaking, DO NOT transcribe room silence!
        if not talking_started:
            self.reset_to_listening()
            return

        with wave.open('input.wav', 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames))
            
        self.set_status("Transcribing...", "yellow")
        self.post_ui(self._set_widget_attr, self.lbl_mic_status, "text", "Mic: Transcribing...", "text_color", "#f1c40f")
        try:
            t_trans_start = time.time()
            segments, _ = self.whisper_model.transcribe(
                "input.wav",
                beam_size=5,
                language="en",
                initial_prompt="Jarvis, Hey Jarvis, LeetCode, DSA, Python, Firefox, YouTube, Chrome, binary search, algorithms, games, brightness.",
                condition_on_previous_text=False
            )
            raw_text = "".join(segment.text for segment in segments).strip()
            t_trans_end = time.time()
            
            stt_latency = t_trans_end - t_trans_start
            audio_duration = len(frames) * self.CHUNK / self.RATE
            speedup = (audio_duration / stt_latency) if stt_latency > 0 else 0.0
            self.set_stt_metrics(stt_latency, speedup)

            # Silence hallucination filter
            HALLUCINATIONS = [
                "thanks for watching", "thank you for watching", "see you next time",
                "subscribe for more", "like and subscribe", "please subscribe",
                "thank you", "bye", "you", "..."
            ]
            clean_lower = re.sub(r'[^a-zA-Z0-9\s]', '', raw_text.lower()).strip()
            if any(clean_lower == h or clean_lower.startswith(h) for h in HALLUCINATIONS) and len(clean_lower.split()) < 7:
                print(f"Discarded Whisper silence hallucination: '{raw_text}'")
                self.reset_to_listening()
                return

            user_text = re.sub(r'\b(jervis|travis|service|jarves|charvis)\b', 'Jarvis', raw_text, flags=re.IGNORECASE).strip()
            
            if user_text and len(user_text) > 1:
                lower_text = user_text.lower()
                if "bye" in lower_text or "terminate" in lower_text or "go to sleep" in lower_text:
                    self.update_chat("You", user_text, "white")
                    self.update_chat("Jarvis", "Goodbye! Have a great day.", "yellow")
                    self.tts_queue.put("Goodbye! Have a great day.")
                else:
                    self.process_user_input(user_text)
            else:
                self.reset_to_listening()
        except Exception as e:
            print("Transcription error:", e)
            self.reset_to_listening()

    def send_text(self, event=None):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, 'end')
            is_processing.set()
            threading.Thread(target=self.process_user_input, args=(text,), daemon=True).start()

    def process_user_input(self, text):
        is_processing.set()
        self.stop_event.clear()
        
        # 1. Direct tool & intent execution (hardware controls, vision, apps, web, games)
        handled, action_msg, speech_response, needs_llm = tools.detect_and_run_intent(text)
        if handled:
            self.update_chat("You", text, "white")
            if action_msg:
                self.update_chat("System", action_msg, "#3498db")
            if speech_response and not needs_llm:
                self.update_chat("Jarvis", speech_response, "#f1c40f")
                self.tts_queue.put(speech_response)
                self.set_status("Action completed.", "lightgreen")
                return

        # 2. If screen vision was triggered, inject on-screen code/text into prompt
        actual_prompt = text
        if handled and needs_llm:
            screen_data = tools.inspect_screen()
            actual_prompt = f"{text}\n\n[Current On-Screen Text and Code Captured via Vision OCR]:\n{screen_data[:2000]}"
            self.set_status("Analyzing screen...", "#00d2d3")
        else:
            if not handled:
                self.update_chat("You", text, "white")
            self.set_status("Jarvis is thinking...", "yellow")

        self.set_generation_metrics(0.0, 0.0, 0, "Generating...")
        
        HISTORY.append({"role": "user", "content": actual_prompt})
        
        try:
            self.start_assistant_message()
            self.set_status("Jarvis is responding...", "yellow")
            
            gen_start_time = time.time()
            token_count = 0
            
            response_stream = self.llm.create_chat_completion(
                messages=HISTORY,
                max_tokens=1024,
                temperature=0.6,
                repeat_penalty=1.15,
                stream=True
            )
            
            full_reply = ""
            speech_buffer = ""
            
            for chunk in response_stream:
                if self.stop_event.is_set() or self._is_closed:
                    break
                delta = chunk['choices'][0].get('delta', {})
                token = delta.get('content', '')
                if not token:
                    continue
                
                token_count += 1
                now = time.time()
                elapsed = now - gen_start_time
                tps = token_count / elapsed if elapsed > 0 else 0.0
                
                if token_count % 3 == 0:
                    self.set_generation_metrics(tps, elapsed, token_count, "Generating...")

                full_reply += token
                self.append_chat_token(token)
                
                speech_buffer += token
                
                if "```" in speech_buffer:
                    parts = speech_buffer.split("```")
                    if len(parts) >= 3:
                        speech_buffer = parts[0] + " I have placed the code implementation on your screen. " + parts[-1]
                
                if "```" not in speech_buffer and any(speech_buffer.endswith(punct) for punct in ['. ', '? ', '! ', '.\n', '?\n', '!\n', '\n\n']):
                    to_speak = self.clean_for_speech(speech_buffer)
                    if to_speak and len(to_speak) > 3:
                        self.tts_queue.put(to_speak)
                    speech_buffer = ""
            
            total_elapsed = time.time() - gen_start_time
            final_tps = token_count / total_elapsed if total_elapsed > 0 else 0.0
            self.finish_assistant_message()
            self.set_generation_metrics(final_tps, total_elapsed, token_count, "Done")
            
            if not self.stop_event.is_set() and speech_buffer.strip():
                to_speak = self.clean_for_speech(speech_buffer)
                if to_speak:
                    self.tts_queue.put(to_speak)
                    
            if not self.stop_event.is_set():
                HISTORY.append({"role": "assistant", "content": full_reply})
                
                found, action_msg, clean_text = tools.parse_and_execute_tool(full_reply)
                if found and action_msg:
                    self.update_chat("System", action_msg, "#3498db")
                    announcement = action_msg.replace("[Action: ", "").replace("]", "")
                    self.tts_queue.put(announcement)
            
        except Exception as e:
            self.update_chat("Error", str(e), "red")
            self.reset_to_listening()

if __name__ == "__main__":
    app = JarvisGUI()
    app.mainloop()
