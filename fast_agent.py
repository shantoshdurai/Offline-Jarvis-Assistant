"""Fast Agent Engine for Jarvis AI.

Features:
- Sub-50ms streaming STT with NVIDIA Parakeet-EOU-120M INT8 ONNX
- Automatic Whisper base.en fallback
- Direct YouTube Video Player (resolves top video ID and plays directly)
- DeepSeek 4.1 Flash via OpenRouter with automatic zero-cost fallback to openrouter/free
- Modality awareness: [Voice Input] vs [Typed Input]
- Push-to-talk hotkeys: Ctrl+Shift+Space or Ctrl+Alt+J (avoids Ctrl+Win / Alt+Space conflicts)
- Continuous wake-word engine: 'Hey Jarvis'
- Real-time Title Bar visual telemetry (mic volume, wake score, ready state)
- Dynamic ambient noise calibration for laptop microphone arrays
- Edge-TTS neural speech with offline Windows SAPI fallback
- Full local PC control tools (apps, files, folders, commands, screen OCR, volume, LeetCode)
"""

import os
import sys

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import time
import json
import queue
import asyncio
import threading
import subprocess
import urllib.request
import urllib.parse
import uuid
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pyaudio
import pygame
import winsound
import ctypes
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path=None):
        if not path:
            path = ".env"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

# Local modules
import tools
from parakeet_stt import ParakeetEOU

# Load environment configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "openrouter/free")
WAKE_THRESHOLD = float(os.getenv("WAKE_THRESHOLD", "0.25"))

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1280

# Pygame mixer for audio playback
try:
    pygame.mixer.init()
except Exception:
    pass

SYSTEM_PROMPT = """You are Jarvis, Shantosh's lightning-fast personal AI assistant and pair programmer running on his Windows PC.
You are powered by DeepSeek 4.1 Flash. Always identify as Jarvis.

MODALITY AWARENESS:
Shantosh communicates with you via two tagged input types:
1. [Voice Input]: Shantosh spoke to you aloud via microphone, transcribed in real time by your NVIDIA Parakeet-EOU speech engine. You CAN hear him! When he asks if you hear him via voice, confirm you hear him loud and clear through the mic.
2. [Typed Input]: Shantosh typed directly into your terminal on his keyboard. You know with 100% certainty that he typed it, not spoke it.

VOICE & RESPONSE RULES:
- Speak directly, concisely, and naturally. Usually 1-2 spoken sentences.
- When the user asks to play a video, song, or music on YouTube, invoke the play_video tool.
- When asked to open an application, folder, change volume, or run a command, ALWAYS invoke the corresponding tool.
- Never read raw programming syntax or markdown formatting out loud.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "play_video",
            "description": "Play a video, music, or song directly on YouTube (e.g. '10 hours loki music marvel', 'lofi hip hop', 'interstellar theme'). Resolves top video and immediately plays it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Name or query of the video/music to play."
                    },
                    "browser": {
                        "type": "string",
                        "description": "Browser to use: 'default', 'firefox', or 'chrome'.",
                        "default": "default"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Launch an application on the PC (e.g. firefox, chrome, code/vscode, notepad, terminal/cmd, calc, explorer, blender, godot).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of application."
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a website or search query in the browser (e.g. LeetCode, GitHub, Google search).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL or search query."
                    },
                    "browser": {
                        "type": "string",
                        "description": "Browser to use.",
                        "default": "default"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_leetcode",
            "description": "Open LeetCode problem or daily challenge.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "LeetCode problem title, slug, or 'daily'."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_folder",
            "description": "Open a folder in Windows Explorer (e.g. downloads, desktop, documents, pictures).",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Folder name or absolute path."
                    }
                },
                "required": ["folder_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the user's screen.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_control",
            "description": "Control system volume or lock the screen (volume_up, volume_down, mute, lock).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action: 'volume_up', 'volume_down', 'mute', 'lock'."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a terminal / PowerShell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "PowerShell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search local files in user directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Filename or substring to search for."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a local file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file."
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]


def dispatch_tool_call(name: str, args: Dict[str, Any]) -> str:
    """Execute tool using tools.py implementation."""
    try:
        if name == "play_video":
            return tools.play_video(args.get("query", ""), args.get("browser"))
        elif name == "open_app":
            return tools.open_app(args.get("app_name", ""))
        elif name == "open_url":
            return tools.open_url(args.get("url", ""), args.get("browser"))
        elif name == "open_leetcode":
            action, _ = tools.open_leetcode(args.get("query", ""))
            return action
        elif name == "open_folder":
            return tools.open_folder(args.get("folder_path", ""))
        elif name == "take_screenshot":
            return tools.take_screenshot()
        elif name == "system_control":
            act = args.get("action", "")
            if act in ("volume_up", "volume_down", "mute"):
                return tools.adjust_volume(act.replace("volume_", ""))
            elif act == "lock":
                ctypes.windll.user32.LockWorkStation()
                return "Locked Windows workstation."
            return f"Unknown system action: {act}"
        elif name == "run_command":
            return tools.execute_command(args.get("command", ""))
        elif name == "search_files":
            return tools.search_local_files(args.get("query", ""))
        elif name == "read_file":
            return tools.read_file_content(args.get("file_path", ""))
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error executing {name}: {e}"


class FastAgent:
    def __init__(self):
        print("============================================================")
        print("  Jarvis Fast Agent (DeepSeek 4.1 Flash + Parakeet-EOU INT8)")
        print("============================================================\n")

        # 1. Check API Key
        if not OPENROUTER_API_KEY:
            print("[Warning] OPENROUTER_API_KEY is not set in .env! LLM queries may fail.")
            print("Please create a .env file with OPENROUTER_API_KEY=your_key_here\n")

        # 2. Load Parakeet EOU
        print("Loading NVIDIA Parakeet-EOU-120M INT8 speech recognizer...")
        self.stt = None
        try:
            self.stt = ParakeetEOU()
            print("[OK] Parakeet-EOU ready (<EOU> end-of-turn detection active)")
        except Exception as e:
            print(f"[Notice] Parakeet-EOU model not found or error ({e}).")
            print("Falling back to Whisper. (To use Parakeet, run: python download_parakeet.py)")

        # 3. Whisper fallback
        self.whisper_model = None

        # 4. Load OpenWakeWord
        print("Loading wake word engine ('Hey Jarvis')...")
        try:
            from openwakeword.model import Model
            self.oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            print("[OK] Wake word engine active")
        except Exception as e:
            print(f"[Warning] OpenWakeWord error ({e}). Hotkey push-to-talk will be used.")
            self.oww = None

        # 5. Initialize PyAudio stream
        print("Initializing microphone stream...")
        self.audio = pyaudio.PyAudio()
        self.mic_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        # 6. Calibrate noise floor for laptop microphones
        print("Calibrating microphone ambient noise floor (0.5s)...")
        calib_frames = []
        for _ in range(int(RATE / CHUNK * 0.5)):
            data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
            calib_frames.append(np.frombuffer(data, dtype=np.int16))
        all_calib = np.concatenate(calib_frames)
        self.noise_floor = int(np.abs(all_calib).mean())
        self.speech_threshold = max(800, int(self.noise_floor * 1.35))
        print(f"[OK] Calibrated noise floor: {self.noise_floor} | Speech threshold: {self.speech_threshold}")

        # 7. State & Synchronization
        self.is_listening = threading.Event()
        self.is_speaking = threading.Event()
        self.command_queue = queue.Queue()
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # 8. SAPI offline voice fallback
        try:
            import pyttsx3
            self.sapi_engine = pyttsx3.init()
            self.sapi_engine.setProperty("rate", 185)
        except Exception:
            self.sapi_engine = None

        # 9. Global Hotkey Listener (Ctrl+Shift+Space and Ctrl+Alt+J)
        self.setup_hotkey()

    def get_whisper(self):
        """Lazy loader for faster-whisper fallback."""
        if self.whisper_model is None:
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
        return self.whisper_model

    def play_chime(self, sound_type: str = "start"):
        """Audible feedback chime."""
        try:
            if sound_type == "start":
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sound_type == "end":
                winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass

    def setup_hotkey(self):
        """Set up push-to-talk hotkeys (Ctrl+Shift+Space and Ctrl+Alt+J)."""
        def on_hotkey():
            if not self.is_listening.is_set() and not self.is_speaking.is_set():
                print("\n[Push-to-Talk Hotkey Triggered]")
                self.is_listening.set()
                self.command_queue.put("HOTKEY")

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                '<ctrl>+<shift>+<space>': on_hotkey,
                '<ctrl>+<alt>+j': on_hotkey,
            })
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
            print("[OK] Push-to-talk active: Ctrl+Shift+Space or Ctrl+Alt+J")
        except Exception as e:
            print(f"[Warning] Hotkey setup: {e}")

    def tts_speak(self, text: str):
        """Neural speech output using Edge-TTS with instant Windows SAPI fallback."""
        if not text.strip():
            return

        clean_text = text.replace("```", "").replace("**", "").replace("*", "").strip()
        print(f"\n🤖 Jarvis: {clean_text}\n")

        self.is_speaking.set()
        temp_audio = os.path.join(
            os.path.expanduser("~"),
            "AppData", "Local", "Temp",
            f"jarvis_voice_{uuid.uuid4().hex[:8]}.mp3"
        )

        async def generate_speech():
            import edge_tts
            comm = edge_tts.Communicate(clean_text, voice="en-GB-RyanNeural", rate="+10%")
            await comm.save(temp_audio)

        try:
            asyncio.run(generate_speech())
            if os.path.exists(temp_audio):
                pygame.mixer.music.load(temp_audio)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.04)
                pygame.mixer.music.unload()
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass
        except Exception as e:
            # Instant SAPI offline fallback
            try:
                if self.sapi_engine:
                    self.sapi_engine.say(clean_text)
                    self.sapi_engine.runAndWait()
                else:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.setProperty("rate", 185)
                    engine.say(clean_text)
                    engine.runAndWait()
            except Exception as e2:
                print(f"(Speech playback error: {e2})")
        finally:
            self.is_speaking.clear()

    def query_llm(self, user_text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Query DeepSeek 4.1 Flash via OpenRouter with automatic fallback to free models."""
        self.history.append({"role": "user", "content": user_text})

        req_body = {
            "model": OPENROUTER_MODEL,
            "messages": self.history[-8:],
            "tools": TOOL_DEFINITIONS,
            "temperature": 0.3,
            "max_tokens": 300
        }

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/shantoshdurai/Offline-Jarvis-Assistant",
                "X-Title": "Offline Jarvis Assistant"
            },
            data=json.dumps(req_body).encode("utf-8")
        )

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                res = json.loads(resp.read().decode("utf-8"))
            choice = res["choices"][0]["message"]
            content = choice.get("content") or ""
            tool_calls = choice.get("tool_calls") or []
            return content, tool_calls
        except Exception as e:
            print(f"⚠️ Primary model error ({e}), switching to free fallback model ({FALLBACK_MODEL})...")
            req_body["model"] = FALLBACK_MODEL
            req_fallback = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                data=json.dumps(req_body).encode("utf-8")
            )
            try:
                with urllib.request.urlopen(req_fallback, timeout=12) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                choice = res["choices"][0]["message"]
                return choice.get("content") or "", choice.get("tool_calls") or []
            except Exception as e2:
                return f"Sorry, network error: {e2}", []

    def execute_command_pipeline(self, user_text: str, source: str = "voice"):
        """Process user command, call LLM & tools, and speak reply."""
        if source == "voice":
            print(f"\n📝 Heard (Voice): \"{user_text}\"")
            prompt = f"[Voice Input]: {user_text}"
        else:
            print(f"\n⌨️ Typed (Console): \"{user_text}\"")
            prompt = f"[Typed Input]: {user_text}"

        t_start = time.time()
        content, tool_calls = self.query_llm(prompt)
        t_llm = time.time() - t_start

        tool_results = []
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}
                print(f"⚡ [Tool Call]: {name}({args})")
                res = dispatch_tool_call(name, args)
                print(f"   ↳ {res}")
                tool_results.append(res)

        spoken_response = content.strip()
        if not spoken_response and tool_results:
            spoken_response = tool_results[0]
        elif not spoken_response:
            spoken_response = "Done."

        self.history.append({"role": "assistant", "content": spoken_response})
        print(f"⚡ Latency: LLM {t_llm:.2f}s")
        self.tts_speak(spoken_response)

    def record_audio(self, max_duration: float = 12.0, silence_limit: float = 1.4, start_timeout: float = 5.0) -> np.ndarray:
        """Record audio with start/end chimes and automatic silence cutoff."""
        print("\n🎙️  Listening! Speak your command...")
        self.play_chime("start")

        frames = []
        silent_chunks = 0
        chunks_per_sec = RATE / CHUNK
        max_silent_chunks = int(silence_limit * chunks_per_sec)
        max_total_chunks = int(max_duration * chunks_per_sec)
        timeout_chunks = int(start_timeout * chunks_per_sec)

        talking_started = False

        # Flush stale mic buffer
        while self.mic_stream.get_read_available() > 0:
            self.mic_stream.read(self.mic_stream.get_read_available(), exception_on_overflow=False)

        for i in range(max_total_chunks):
            data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()

            # Dynamic voice detection based on calibrated threshold
            if volume > self.speech_threshold:
                talking_started = True
                silent_chunks = 0
            elif talking_started:
                silent_chunks += 1

            if talking_started and silent_chunks > max_silent_chunks:
                break
            if not talking_started and i > timeout_chunks:
                break

        self.play_chime("end")
        if not frames:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate([np.frombuffer(f, dtype=np.int16) for f in frames])

    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe speech using Parakeet-EOU INT8, with Whisper fallback."""
        if len(audio_data) < RATE * 0.4:
            return ""

        # Try Parakeet first
        if self.stt is not None:
            try:
                t0 = time.time()
                text = self.stt.transcribe(audio_data)
                stt_time = time.time() - t0
                if text.strip():
                    print(f"⚡ STT (Parakeet-EOU INT8): \"{text}\" ({stt_time:.2f}s)")
                    return text.strip()
            except Exception as e:
                print(f"[Notice] Parakeet decode issue ({e}), trying Whisper...")

        # Whisper fallback
        try:
            whisper = self.get_whisper()
            import tempfile, wave
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                wav_path = tf.name
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(audio_data.tobytes())

            segments, _ = whisper.transcribe(wav_path, beam_size=1)
            whisper_text = "".join([s.text for s in segments]).strip()
            try:
                os.remove(wav_path)
            except Exception:
                pass
            if whisper_text:
                print(f"⚡ STT (Whisper fallback): \"{whisper_text}\"")
                return whisper_text
        except Exception:
            pass

        return ""

    def wake_word_listener(self):
        """Background thread constantly listening for 'Hey Jarvis' on mic stream."""
        if self.oww is None:
            return

        while True:
            try:
                if not self.is_listening.is_set() and not self.is_speaking.is_set():
                    data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    vol = int(np.abs(audio_data).mean())
                    prediction = self.oww.predict(audio_data)
                    max_score = max(prediction.values()) if prediction else 0.0

                    # Real-time mic volume and wake score in title bar
                    title = f"Jarvis AI | Mic Vol: {vol} | Hey Jarvis: {max_score:.2f} | Ctrl+Shift+Space to talk"
                    ctypes.windll.kernel32.SetConsoleTitleW(title)

                    if max_score > WAKE_THRESHOLD:
                        print(f"\n[Wake Word Detected: Hey Jarvis (score={max_score:.2f})]")
                        self.oww.reset()
                        self.is_listening.set()
                        self.command_queue.put("WAKE_WORD")
                else:
                    time.sleep(0.08)
            except OSError:
                break
            except Exception:
                time.sleep(0.5)

    def run(self):
        """Main assistant lifecycle loop."""
        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)

        print("\n" + "=" * 60)
        print(" Jarvis is Online.")
        print(" - Say 'Hey Jarvis' or press 'Ctrl+Shift+Space' / 'Ctrl+Alt+J'")
        print(" - Or type your command below and press Enter.")
        print("=" * 60 + "\n")

        # Start wake word listener thread
        listener_thread = threading.Thread(target=self.wake_word_listener, daemon=True)
        listener_thread.start()

        # Keyboard terminal input thread
        def terminal_input_worker():
            while True:
                try:
                    cmd = input().strip()
                    if cmd and not self.is_listening.is_set():
                        self.execute_command_pipeline(cmd, source="typed")
                except (EOFError, KeyboardInterrupt):
                    break

        t_input = threading.Thread(target=terminal_input_worker, daemon=True)
        t_input.start()

        try:
            while True:
                try:
                    trigger = self.command_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if trigger in ("HOTKEY", "WAKE_WORD"):
                    ctypes.windll.kernel32.SetConsoleTitleW("Jarvis AI | 🎙️ Listening...")
                    audio_data = self.record_audio()
                    self.is_listening.clear()

                    if len(audio_data) > 0:
                        ctypes.windll.kernel32.SetConsoleTitleW("Jarvis AI | 🧠 Thinking...")
                        user_text = self.transcribe(audio_data)
                        if user_text:
                            self.execute_command_pipeline(user_text, source="voice")

                    ctypes.windll.kernel32.SetConsoleTitleW("Jarvis AI | Ready")

        except KeyboardInterrupt:
            print("\nShutting down Jarvis...")
        finally:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
            self.audio.terminate()


if __name__ == "__main__":
    agent = FastAgent()
    agent.run()
