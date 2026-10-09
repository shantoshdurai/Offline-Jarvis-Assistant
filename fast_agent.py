"""Fast Agent Engine for Jarvis AI.

Features:
- Single-instance IPC architecture on port 49155:
    * 1st launch: Starts silently in Windows notification tray with OpenWhispr-style blue icon
    * 2nd launch (or tray click): Brings up the sleek OpenWhispr modern dark dashboard GUI
- Sub-50ms streaming STT with NVIDIA Parakeet-EOU-120M INT8 ONNX
- Automatic Whisper base.en fallback
- Direct YouTube Video Player (resolves top video ID and plays directly)
- DeepSeek 4.1 Flash via OpenRouter with automatic zero-cost fallback to openrouter/free
- Minimal lightweight system prompt for near-instant cold start
- Modality awareness: [Voice Input] vs [Typed Input]
- Push-to-talk hotkeys: Ctrl+Shift+Space, Ctrl+Alt+J, and Ctrl+Win
- Continuous wake-word engine: 'Hey Jarvis'
- OpenWhispr floating voice pill overlay with live animated waveform equalizer & C5->E5 sound cues
- Minimize-to-tray on 'X' button, clean 1-click 'Stop Jarvis' shutdown
"""

import os
import sys

# Hide console window immediately if not launched with --console
import ctypes
if "--console" not in sys.argv:
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import time
import re
import json
import queue
import socket
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
from overlay_widget import FloatingVoicePill
from dashboard_gui import JarvisDashboard, load_config, save_config

# Base directories & environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

IPC_PORT = 49155
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "openrouter/free")
WAKE_THRESHOLD = float(os.getenv("WAKE_THRESHOLD", "0.22"))

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1280

# Pygame mixer for audio playback
try:
    if not pygame.mixer.get_init():
        pygame.mixer.init()
except Exception:
    pass

# Minimal lightweight system prompt for fastest response and low cold-start latency
SYSTEM_PROMPT = """You are Jarvis, a fast personal voice AI assistant and pair programmer running on Windows.
VOICE & TTS GUIDELINES:
- Every word you output will be spoken aloud to the user via Text-to-Speech (TTS). Speak in 1-2 natural, conversational sentences.
- NEVER include raw URLs (like https://...), query parameters, website links, slashes, or plus signs in spoken replies.
- When asked to close an app, browser, tab, or window, ALWAYS call the close_app tool.
- When asked to shut down, quit, exit, or stop Jarvis, call exit_jarvis. Never lecture about Terminator or give multi-paragraph options.
- When asked to shut down the PC or computer, call system_control(action='shutdown_pc').
- When told to remember facts or notes (e.g. preferences, project details), call save_memory. When asked what you remember, call recall_memory.
- When asked to play music or videos, call play_video.
- When asked to open apps, websites, or folders, call the appropriate tool.
- When asked what apps or software are installed on the PC, call list_installed_apps.
- When asked to run terminal commands, inspect files, or read code, use run_command, search_files, read_file, or list_folder_contents.
- Never read out code blocks, raw markdown, or long technical logs aloud.
CLARIFICATION & CONFIRMATION:
- If a user's voice command is ambiguous, incomplete, or you suspect STT misheard words, ask a concise 1-sentence question to confirm what they meant before taking action.
- If an app name could refer to multiple installed apps, confirm with the user which one they prefer.
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
            "name": "close_app",
            "description": "Close or terminate a running application, browser, or active window (e.g. 'close chrome', 'close firefox', 'close notepad', 'close window').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name or process of application to close (e.g. 'chrome', 'firefox', 'notepad', 'code', 'window')."
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
    },
    {
        "type": "function",
        "function": {
            "name": "list_folder_contents",
            "description": "List files and folders inside common directories or a specified directory (e.g. downloads, desktop, documents, project).",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "Folder to list: 'downloads', 'desktop', 'documents', 'project', or path.",
                        "default": "downloads"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Store a user fact, preference, or note into persistent memory forever (e.g. 'remember that my favorite browser is Firefox', 'save note: project meeting at 3pm').",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact_or_note": {
                        "type": "string",
                        "description": "The fact, preference, or note to remember."
                    }
                },
                "required": ["fact_or_note"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Recall stored facts, preferences, or notes from persistent memory (e.g. 'what is my preferred browser', 'what notes do you have', 'what did I tell you to remember').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or topic to recall, or leave empty for general summary.",
                        "default": ""
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "forget_memory",
            "description": "Forget or remove a specific fact or note from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Fact or note to forget."
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_installed_apps",
            "description": "List software and installed applications discovered on the user's PC (e.g. Antigravity, Blender, Claude, VS Code, Discord, OBS, Unity, Steam).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_query": {
                        "type": "string",
                        "description": "Optional keyword or category to filter apps by.",
                        "default": ""
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exit_jarvis",
            "description": "Completely stop and shut down the Jarvis assistant application when the user asks to 'shut down jarvis', 'exit jarvis', 'quit jarvis', or 'stop jarvis'.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def dispatch_tool_call(name: str, args: Dict[str, Any], agent_ref: Optional[Any] = None) -> str:
    """Execute tool using tools.py and memory_manager implementations."""
    try:
        if name == "play_video":
            return tools.play_video(args.get("query", ""), args.get("browser"))
        elif name == "open_app":
            return tools.open_app(args.get("app_name", ""))
        elif name == "close_app":
            return tools.close_app(args.get("app_name", ""))
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
            elif act in ("shutdown_pc", "shutdown_computer"):
                subprocess.Popen(["shutdown", "/s", "/t", "60"])
                return "Shutting down computer in 60 seconds. Say 'abort shutdown' to cancel."
            elif act in ("abort_shutdown", "cancel_shutdown"):
                subprocess.Popen(["shutdown", "/a"])
                return "Computer shutdown cancelled."
            return f"Unknown system action: {act}"
        elif name == "run_command":
            return tools.execute_command(args.get("command", ""))
        elif name == "search_files":
            return tools.search_local_files(args.get("query", ""))
        elif name == "read_file":
            return tools.read_file_content(args.get("file_path", ""))
        elif name == "list_folder_contents":
            return tools.list_folder_contents(args.get("folder_name", "downloads"))
        elif name == "list_installed_apps":
            return tools.list_installed_apps(args.get("filter_query", ""))
        elif name == "save_memory":
            import memory_manager
            return memory_manager.remember_fact_or_note(args.get("fact_or_note", ""))
        elif name == "recall_memory":
            import memory_manager
            return memory_manager.recall_memories(args.get("query", ""))
        elif name == "forget_memory":
            import memory_manager
            return memory_manager.forget_memory(args.get("target", ""))
        elif name == "exit_jarvis":
            if agent_ref:
                threading.Thread(target=lambda: (time.sleep(1.2), agent_ref.shutdown()), daemon=True).start()
            return "Shutting down Jarvis. Goodbye."
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error executing {name}: {e}"


def check_single_instance(port: int = IPC_PORT) -> bool:
    """Returns True if Jarvis is already running and signaled, False if this is primary."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", port))
        s.sendall(b"SHOW_DASHBOARD\n")
        try:
            s.settimeout(0.6)
            s.recv(1024)
        except Exception:
            pass
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def clean_spoken_text(text: str) -> str:
    """Prepares text for natural human-like speech synthesis by removing URLs,
    symbols, markdown syntax, and technical characters.
    """
    if not text:
        return ""
    s = text.strip()
    # 1. Clean markdown code blocks, backticks, bold, headers, list bullets
    s = re.sub(r'```[\s\S]*?```', '', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    s = re.sub(r'(\*\*|\*|__|_|~~)', '', s)
    s = re.sub(r'^#{1,6}\s+', '', s, flags=re.MULTILINE)
    s = re.sub(r'^\s*[-*+]\s+', '', s, flags=re.MULTILINE)
    s = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', s)

    # 2. Known sites -> conversational names
    s = re.sub(r'https?://(?:www\.)?chatgpt\.com[^\s]*', 'ChatGPT', s, flags=re.IGNORECASE)
    s = re.sub(r'https?://(?:www\.)?youtube\.com[^\s]*', 'YouTube', s, flags=re.IGNORECASE)
    s = re.sub(r'https?://(?:www\.)?github\.com[^\s]*', 'GitHub', s, flags=re.IGNORECASE)
    s = re.sub(r'https?://(?:www\.)?leetcode\.com[^\s]*', 'LeetCode', s, flags=re.IGNORECASE)
    s = re.sub(r'https?://(?:www\.)?google\.com/search\?q=([^\s&]+)[^\s]*', lambda m: urllib.parse.unquote(m.group(1)).replace('+', ' '), s, flags=re.IGNORECASE)

    # 3. Any remaining URLs -> convert to domain voice title
    def clean_generic_url(match):
        raw = match.group(0)
        domain = re.sub(r'^https?://', '', raw, flags=re.IGNORECASE)
        domain = re.sub(r'^www\.', '', domain, flags=re.IGNORECASE)
        domain = domain.split('/')[0].split('?')[0]
        voice_name = re.sub(r'\.(com|org|net|io|ai|co|gov|edu)$', '', domain, flags=re.IGNORECASE)
        return voice_name.capitalize() if voice_name else 'the website'

    s = re.sub(r'https?://[^\s]+', clean_generic_url, s)
    s = re.sub(r'www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s]*', clean_generic_url, s)

    # 4. Clean query artifacts (+ between words) and multiple slashes
    s = re.sub(r'(?<=\w)\+(?=\w)', ' ', s)
    s = re.sub(r'/{2,}', ' ', s)
    s = re.sub(r'\\{2,}', ' ', s)

    # 5. Clean Windows paths to just filename or folder
    s = re.sub(r'[A-Za-z]:\\[^ \n\r\t]+', lambda m: os.path.basename(m.group(0).rstrip('\\/')) or 'file', s)

    # 6. Collapse spaces
    s = re.sub(r'\s+', ' ', s).strip()
    return s


class FastAgent:
    def __init__(self):
        print("============================================================")
        print("  Jarvis Fast Agent (DeepSeek 4.1 Flash + Parakeet-EOU INT8)")
        print("============================================================\n")

        self.is_running = True
        self.is_session_active = False

        # Load persistent configuration
        self.config = load_config()
        self.follow_up_timeout = float(self.config.get("follow_up_timeout", 10.0))
        self.silence_limit = float(self.config.get("silence_limit", 0.55))
        self.sfx_enabled = bool(self.config.get("sfx_enabled", True))
        self.voice_dismissal_enabled = bool(self.config.get("voice_dismissal_enabled", True))
        self.wake_word_enabled = bool(self.config.get("wake_word_enabled", True))

        # 1. Initialize Dashboard GUI
        self.dashboard = JarvisDashboard(
            on_trigger_voice=self.trigger_voice,
            on_send_chat=lambda text: self.execute_command_pipeline(text, source="typed"),
            on_stop_jarvis=self.shutdown,
            on_save_api_key=self.save_api_key,
            on_toggle_wake_word=self.set_wake_word_enabled,
            on_update_settings=self.on_update_settings,
        )

        # 2. OpenWhispr Floating Voice Pill Overlay (attached to CTk root)
        try:
            self.pill = FloatingVoicePill(parent=self.dashboard.root)
            self.pill.sfx_enabled = self.sfx_enabled
            print("[OK] OpenWhispr Floating Voice Pill overlay active")
        except Exception as e:
            print(f"[Notice] Floating overlay error: {e}")
            self.pill = None

        # 3. Speech Recognizer (NVIDIA Parakeet-EOU INT8)
        self.stt = None
        try:
            self.stt = ParakeetEOU()
            print("[OK] Parakeet-EOU INT8 speech engine active")
        except Exception as e:
            print(f"[Notice] Parakeet-EOU error ({e}). Whisper fallback active.")

        self.whisper_model = None

        # 4. OpenWakeWord Model ('Hey Jarvis')
        self.oww = None
        try:
            from openwakeword.model import Model
            self.oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            print("[OK] Continuous Wake Word active ('Hey Jarvis')")
        except Exception as e:
            print(f"[Warning] OpenWakeWord error ({e}).")

        # 5. Microphone Stream
        self.audio = pyaudio.PyAudio()
        self.mic_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        # 6. Ambient Noise Calibration
        calib_frames = []
        for _ in range(int(RATE / CHUNK * 0.4)):
            data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
            calib_frames.append(np.frombuffer(data, dtype=np.int16))
        all_calib = np.concatenate(calib_frames)
        self.noise_floor = int(np.abs(all_calib).mean())
        self.speech_threshold = max(800, int(self.noise_floor * 1.35))
        print(f"[OK] Calibrated noise floor: {self.noise_floor} | Speech threshold: {self.speech_threshold}")

        # 7. State & Queues
        self.is_listening = threading.Event()
        self.is_speaking = threading.Event()
        self.command_queue = queue.Queue()
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # 8. SAPI Voice Fallback
        try:
            import pyttsx3
            self.sapi_engine = pyttsx3.init()
            self.sapi_engine.setProperty("rate", 185)
        except Exception:
            self.sapi_engine = None

        # 9. Register Global Hotkeys
        self.setup_hotkeys()

        # 10. Start IPC Server thread
        self.ipc_thread = threading.Thread(target=self._run_ipc_server, daemon=True)
        self.ipc_thread.start()

        # 11. Start System Tray Icon
        self.tray_thread = threading.Thread(target=self._setup_tray, daemon=True)
        self.tray_thread.start()

        # 12. Start Background Worker Threads
        self.listener_thread = threading.Thread(target=self._wake_word_listener, daemon=True)
        self.listener_thread.start()

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        # 13. Terminal input thread if console is open
        if "--console" in sys.argv:
            self.t_input = threading.Thread(target=self._terminal_input_loop, daemon=True)
            self.t_input.start()

    def set_wake_word_enabled(self, enabled: bool):
        self.wake_word_enabled = enabled
        self.config["wake_word_enabled"] = enabled
        save_config(self.config)

    def on_update_settings(self, new_cfg: Dict[str, Any]):
        self.config.update(new_cfg)
        self.follow_up_timeout = float(self.config.get("follow_up_timeout", 10.0))
        self.silence_limit = float(self.config.get("silence_limit", 0.55))
        self.sfx_enabled = bool(self.config.get("sfx_enabled", True))
        if self.pill:
            self.pill.sfx_enabled = self.sfx_enabled
        self.voice_dismissal_enabled = bool(self.config.get("voice_dismissal_enabled", True))
        self.wake_word_enabled = bool(self.config.get("wake_word_enabled", True))
        save_config(self.config)
        print(f"[Settings Updated] FollowUp={self.follow_up_timeout}s | SilenceLimit={self.silence_limit}s | SFX={self.sfx_enabled} | Dismissal={self.voice_dismissal_enabled}")

    def save_api_key(self, key: str):
        global OPENROUTER_API_KEY
        OPENROUTER_API_KEY = key
        os.environ["OPENROUTER_API_KEY"] = key
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"OPENROUTER_API_KEY={key}\n")
                f.write(f"OPENROUTER_MODEL={OPENROUTER_MODEL}\n")
                f.write(f"FALLBACK_MODEL={FALLBACK_MODEL}\n")
                f.write(f"WAKE_THRESHOLD={WAKE_THRESHOLD}\n")
        except Exception:
            pass

    def _run_ipc_server(self):
        """Single-instance IPC server to handle 2nd launch signals."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("127.0.0.1", IPC_PORT))
            srv.listen(5)
            while self.is_running:
                try:
                    conn, _ = srv.accept()
                    data = conn.recv(1024).decode("utf-8").strip()
                    if data == "SHOW_DASHBOARD":
                        conn.sendall(b"OK\n")
                        self.dashboard.show()
                    elif data == "TRIGGER_VOICE":
                        conn.sendall(b"OK\n")
                        self.trigger_voice()
                    elif data == "STOP":
                        conn.sendall(b"OK\n")
                        self.shutdown()
                    else:
                        conn.sendall(b"OK\n")
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"[Warning] IPC Server bind error: {e}")
        finally:
            try:
                srv.close()
            except Exception:
                pass

    def _setup_tray(self):
        """Windows system tray icon with OpenWhispr blue circular badge."""
        try:
            import pystray
            from PIL import Image, ImageDraw

            def create_tray_image():
                size = 64
                img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                d.rounded_rectangle((4, 10, size - 4, size - 10), radius=16, fill=(14, 116, 224, 255))
                d.ellipse((14, 22, 30, 42), outline=(255, 255, 255, 255), width=3)
                d.ellipse((size - 30, 22, size - 14, 42), outline=(255, 255, 255, 255), width=3)
                d.line((26, 24, size - 26, 40), fill=(255, 255, 255, 255), width=3)
                d.line((26, 40, size - 26, 24), fill=(255, 255, 255, 255), width=3)
                return img

            def on_open_dashboard(icon=None, item=None):
                self.dashboard.show()

            def on_trigger_voice(icon=None, item=None):
                self.trigger_voice()

            def on_quit(icon=None, item=None):
                self.shutdown()

            menu = pystray.Menu(
                pystray.MenuItem('🖥️  Open Dashboard', on_open_dashboard, default=True),
                pystray.MenuItem('🎙️  Push to Talk (Ctrl+Shift+Space)', on_trigger_voice),
                pystray.MenuItem('🛑  Stop Jarvis', on_quit)
            )

            icon_img = create_tray_image()
            self.tray_icon = pystray.Icon("JarvisAgent", icon_img, "Jarvis AI — Voice Copilot", menu)
            self.tray_icon.run()
        except Exception as e:
            print(f"[Notice] System tray icon: {e}")

    def setup_hotkeys(self):
        """Global Hotkeys: Ctrl+Shift+Space, Ctrl+Alt+J, and Ctrl+Win."""
        if keyboard is None:
            return

        def on_ptt():
            self.trigger_voice()

        def toggle_console():
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                is_visible = ctypes.windll.user32.IsWindowVisible(hwnd)
                ctypes.windll.user32.ShowWindow(hwnd, 0 if is_visible else 5)

        hotkey_bindings = {
            '<ctrl>+<shift>+<space>': on_ptt,
            '<ctrl>+<alt>+j': on_ptt,
            '<ctrl>+<alt>+h': toggle_console,
        }

        # Try registering Ctrl+Cmd (Ctrl+Win) safely
        try:
            hotkey_bindings['<ctrl>+<cmd>'] = on_ptt
        except Exception:
            pass

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_bindings)
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
            print("[OK] Hotkeys: Ctrl+Shift+Space | Ctrl+Alt+J | Ctrl+Win (Console: Ctrl+Alt+H)")
        except Exception as e:
            print(f"[Warning] Hotkey setup issue: {e}")

    def trigger_voice(self):
        """Triggers push-to-talk voice recording."""
        if not self.is_speaking.is_set() and not self.is_session_active:
            self.command_queue.put("TRIGGER")

    def play_chime(self, cue_type: str = "wake"):
        """Plays OpenWhispr harmonic chime (wake: C5->E5, sleep: D5->A4)."""
        if not self.sfx_enabled:
            return
        if self.pill:
            self.pill.play_sfx(cue_type)
        else:
            try:
                if cue_type in ("wake", "start"):
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                elif cue_type in ("sleep", "stop"):
                    winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def get_whisper(self):
        if self.whisper_model is None:
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
        return self.whisper_model

    def record_audio(self, max_duration: float = 12.0, silence_limit: Optional[float] = None, start_timeout: Optional[float] = None) -> np.ndarray:
        """Records voice with live waveform equalizer on floating pill."""
        if silence_limit is None:
            silence_limit = self.silence_limit
        if start_timeout is None:
            start_timeout = self.follow_up_timeout

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

            # Stream live volume level to floating pill waveform
            if self.pill:
                norm = min(1.0, max(0.0, (volume - self.noise_floor) / max(600, self.speech_threshold - self.noise_floor + 200)))
                self.pill.update_volume(norm)

            if volume > self.speech_threshold:
                if not talking_started:
                    talking_started = True
                    if self.pill:
                        self.pill.set_state("recording")
                silent_chunks = 0
            elif talking_started:
                silent_chunks += 1

            if talking_started and silent_chunks > max_silent_chunks:
                break
            if not talking_started and i > timeout_chunks:
                break

        if not talking_started or not frames:
            return np.zeros(0, dtype=np.int16)

        return np.concatenate([np.frombuffer(f, dtype=np.int16) for f in frames])

    def transcribe(self, audio_data: np.ndarray) -> str:
        """Transcribe speech using Parakeet-EOU INT8, with Whisper fallback."""
        if len(audio_data) < RATE * 0.4:
            return ""

        # Parakeet-EOU INT8
        if self.stt is not None:
            try:
                t0 = time.time()
                text = self.stt.transcribe(audio_data)
                if text.strip():
                    print(f"⚡ STT (Parakeet-EOU): \"{text.strip()}\" ({time.time()-t0:.2f}s)")
                    return text.strip()
            except Exception:
                pass

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
                return whisper_text
        except Exception:
            pass

        return ""

    def query_llm(self, user_text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Query DeepSeek 4.1 Flash via OpenRouter with automatic zero-cost fallback."""
        import memory_manager
        mem_ctx = memory_manager.get_memory_context_string()
        sys_content = SYSTEM_PROMPT + (f"\n\n{mem_ctx}" if mem_ctx else "")
        self.history[0] = {"role": "system", "content": sys_content}

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
            print(f"⚠️ Primary model error ({e}), switching to fallback ({FALLBACK_MODEL})...")
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
        """Processes user command, calls LLM & tools, speaks reply, and updates dashboard."""
        clean_text = user_text.lower().strip(" .,?!\"'")
        if clean_text in ("", "mmhm", "mhm", "uh", "um", "ah", "hm", "huh", "yeah", "ok", "okay") or clean_text in {"you", "the", "a", "i", "oh", "so", "thank you", "thanks for watching"}:
            if self.pill:
                self.pill.set_state("idle")
            return

        if self.is_dismissal_command(clean_text):
            self.dashboard.add_interaction(user_text, "Standing by.", source=source, tool="sleep")
            if self.pill:
                self.pill.set_state("speaking")
            self.tts_speak("Standing by.")
            if self.is_session_active:
                self.is_session_active = False
            return

        if self.pill:
            self.pill.set_state("processing")

        prompt = f"[Voice Input]: {user_text}" if source == "voice" else f"[Typed Input]: {user_text}"
        content, tool_calls = self.query_llm(prompt)

        tool_results = []
        executed_tool_name = ""
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}
                print(f"⚡ [Tool]: {name}({args})")
                res = dispatch_tool_call(name, args, agent_ref=self)
                tool_results.append(res)
                executed_tool_name = name

        spoken_response = content.strip()
        if not spoken_response and tool_results:
            spoken_response = " ".join([r for r in tool_results if r])
        elif not spoken_response:
            spoken_response = "Done."

        # Prepare clean speech for natural TTS voice delivery
        cleaned_speech = clean_spoken_text(spoken_response)

        self.history.append({"role": "assistant", "content": spoken_response})

        # Add interaction to Dashboard GUI feed
        self.dashboard.add_interaction(
            user_text=user_text,
            response=spoken_response,
            source=source,
            tool=executed_tool_name
        )

        if self.pill:
            self.pill.set_state("speaking")

        self.tts_speak(cleaned_speech)

    def tts_speak(self, text: str):
        """Neural Edge-TTS speech with instant offline SAPI fallback."""
        clean_text = clean_spoken_text(text)
        if not clean_text:
            return

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
        except Exception:
            # SAPI fallback
            try:
                if self.sapi_engine:
                    self.sapi_engine.say(clean_text)
                    self.sapi_engine.runAndWait()
            except Exception:
                pass
        finally:
            # Echo prevention
            time.sleep(0.35)
            try:
                while self.mic_stream.get_read_available() > 0:
                    self.mic_stream.read(self.mic_stream.get_read_available(), exception_on_overflow=False)
            except Exception:
                pass
            if self.oww is not None:
                self.oww.reset()
            while not self.command_queue.empty():
                try:
                    self.command_queue.get_nowait()
                except queue.Empty:
                    break
            self.is_speaking.clear()
            if self.pill:
                if self.is_session_active:
                    self.pill.set_state("listening")
                else:
                    self.pill.set_state("idle")

    def is_dismissal_command(self, text: str) -> bool:
        """Detect natural voice sleep / dismissal commands for Jarvis itself.
        Never triggers if user is referring to an application, window, tab, or file.
        """
        if not self.voice_dismissal_enabled:
            return False

        clean = text.lower().strip(" .,?!\"'")
        words = clean.split()
        if not words or len(words) > 12:
            return False

        entity_guards = {
            "chrome", "firefox", "edge", "browser", "window", "tab", "tabs",
            "app", "application", "file", "files", "folder", "download", "downloads",
            "youtube", "video", "music", "song", "screen", "process", "program",
            "code", "terminal", "powershell", "cmd", "notepad", "calculator", "calc",
            "spotify", "blender", "pc", "laptop", "computer"
        }
        if any(w in entity_guards for w in words):
            return False

        action_guards = {"open", "play", "search", "show", "read", "run", "launch", "kill", "find", "check"}
        if any(w in action_guards for w in words):
            return False

        # Phonetic STT mishearings of "terminate yourself"
        if any(p in clean for p in ["terminator self", "terminate yourself", "terminal yourself", "terminate your self", "terminator yourself"]):
            return True

        # Goodbye / Bye endings (e.g. "no thanks for that bye bye", "thanks bye", "okay bye bye")
        if clean.endswith("bye") or clean.endswith("bye bye") or clean.endswith("goodbye"):
            return True

        # Direct shutdown / turn off requests directed at Jarvis
        if "shut down" in clean or "turn off" in clean or clean in ("off", "off jarvis", "shut off", "power off"):
            return True

        exact_phrases = {
            # Silence and dismissals
            "nothing", "say nothing", "no nothing", "it's nothing", "its nothing",
            "nothing for now", "nothing else", "no nothing else", "nothing jarvis",
            "say nothing jarvis", "nothing thank you", "nothing thanks",
            "off", "off jarvis", "turn off", "shut off", "power off",
            "never mind", "nevermind", "never mind jarvis", "nevermind jarvis",
            "stop", "stop jarvis", "stop it", "stop talking", "stop speaking",
            "quiet", "be quiet", "quiet now", "quiet jarvis", "shh", "shush", "shut up",
            "cancel", "abort",
            # Standard farewells
            "that's all", "thats all", "that is all",
            "that's all bye", "thats all bye", "that is all bye",
            "that's all for now", "thats all for now", "that is all for now",
            "that will be all", "thats everything", "that's everything",
            "bye", "goodbye", "bye bye", "ok bye", "okay bye", "bye jarvis", "goodbye jarvis",
            "go to sleep", "sleep now", "sleep jarvis",
            "terminate yourself", "dismiss yourself", "stop listening",
            "dismiss", "stand by", "stand down", "sleep"
        }
        if clean in exact_phrases:
            return True

        patterns = [
            r'^(?:no\s+|ok\s+|okay\s+)?(?:say\s+)?nothing(?:\s+else)?(?:\s+for\s+now)?(?:\s+jarvis)?(?:\s+thanks|\s+thank\s+you)?$',
            r'^(?:never\s*mind|nevermind)(?:\s+jarvis)?$',
            r'^(?:be\s+)?quiet(?:\s+now)?(?:\s+jarvis)?$',
            r'^(?:off|power\s+off|shut\s+off)(?:\s+jarvis)?$',
            r'^(?:stop\s+talking|stop\s+speaking|stop)(?:\s+jarvis)?$',
            r'^(?:ok\s+|okay\s+|no\s+)?(?:thanks\s+|thank\s+you\s+)?(?:that\'s\s+all|thats\s+all|that\s+is\s+all)(?:\s+bye)?(?:\s+jarvis)?(?:\s+for\s+now)?$',
            r'^(?:ok\s+|okay\s+|no\s+)?(?:thanks\s+|thank\s+you\s+)?(?:bye|goodbye|bye\s+bye)(?:\s+jarvis)?(?:\s+for\s+now)?$',
            r'^(?:and\s+then\s+|i\s+want\s+you\s+to\s+|please\s+)?(?:go\s+to\s+sleep|sleep|shut\s+down|terminate\s+yourself|dismiss\s+yourself|stop\s+listening)(?:\s+jarvis)?(?:\s+now)?$'
        ]
        for pat in patterns:
            if re.match(pat, clean):
                return True
        return False

    def handle_conversation_session(self):
        """Active conversational session loop.
        Listens, responds, and remains open for follow-up questions
        for up to follow_up_timeout seconds (default 10s) before going to sleep.
        """
        self.is_session_active = True
        self.is_listening.set()

        # Play wake chime ONCE when session begins
        if self.sfx_enabled:
            self.play_chime("wake")

        # Initial turn timeout
        current_timeout = max(5.0, self.follow_up_timeout)

        # Ambient silence hallucinations common in Whisper / Parakeet
        ambient_hallucinations = {
            "you", "the", "a", "i", "oh", "so", "thank you", "thank you.",
            "thanks for watching", "thank you for watching", "thanks for watching.",
            "subtitles by", "subtitle by", "amara.org", "..."
        }

        while self.is_running and self.is_session_active:
            if self.pill:
                self.pill.set_state("listening")

            audio_data = self.record_audio(
                max_duration=12.0,
                silence_limit=self.silence_limit,
                start_timeout=current_timeout
            )

            if len(audio_data) == 0:
                print(f"[Session idle for {current_timeout:.1f}s -> Entering standby sleep]")
                break

            # Reject low-energy ambient breaths / mic pops
            avg_volume = float(np.abs(audio_data).mean()) if len(audio_data) > 0 else 0
            audio_duration = len(audio_data) / RATE
            if audio_duration < 0.45 or avg_volume < self.noise_floor * 1.15:
                print(f"[Low energy/ambient breath ignored ({audio_duration:.2f}s, vol={avg_volume:.1f})]")
                continue

            if self.pill:
                self.pill.set_state("processing")

            user_text = self.transcribe(audio_data)
            clean_text = user_text.lower().strip(" .,?!\"'")

            if not clean_text or clean_text in ambient_hallucinations or clean_text in ("", "mmhm", "mhm", "uh", "um", "ah", "hm", "huh"):
                print(f"[Ignored ambient noise/hallucination: '{user_text}']")
                continue

            # Voice dismissal / sleep check
            if self.is_dismissal_command(clean_text):
                print(f"[Voice Dismissal: '{user_text}'] -> Entering standby sleep")
                self.dashboard.add_interaction(user_text, "Standing by.", source="voice", tool="sleep")
                if self.pill:
                    self.pill.set_state("speaking")
                self.tts_speak("Standing by.")
                break

            # Execute normal command
            self.execute_command_pipeline(user_text, source="voice")

            # After response, keep session open for follow_up_timeout (default 10s)
            current_timeout = self.follow_up_timeout

        # Terminate session & enter standby sleep
        self.is_session_active = False
        if self.pill:
            self.pill.set_state("idle")
        if self.sfx_enabled:
            self.play_chime("sleep")
        self.is_listening.clear()

    def _wake_word_listener(self):
        """Continuous mic listening for 'Hey Jarvis'."""
        if self.oww is None:
            return

        while self.is_running:
            try:
                if self.wake_word_enabled and not self.is_listening.is_set() and not self.is_speaking.is_set() and not self.is_session_active:
                    data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    prediction = self.oww.predict(audio_data)
                    score = max(prediction.values()) if prediction else 0.0

                    if score > WAKE_THRESHOLD:
                        print(f"\n[Wake Word: Hey Jarvis (score={score:.2f})]")
                        self.oww.reset()
                        self.is_listening.set()
                        self.command_queue.put("TRIGGER")
                else:
                    time.sleep(0.08)
            except OSError:
                break
            except Exception:
                time.sleep(0.5)

    def _worker_loop(self):
        """Background loop executing queued voice triggers."""
        while self.is_running:
            try:
                trigger = self.command_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if trigger == "TRIGGER":
                self.handle_conversation_session()

    def _terminal_input_loop(self):
        """Console keyboard input loop when --console is active."""
        while self.is_running:
            try:
                cmd = input().strip()
                if cmd and not self.is_listening.is_set():
                    self.execute_command_pipeline(cmd, source="typed")
            except (EOFError, KeyboardInterrupt):
                break

    def shutdown(self):
        """Gracefully terminate Jarvis agent, destroy all UI widgets, and exit process."""
        self.is_running = False

        # 1. Immediately hide and destroy the floating voice pill
        try:
            if hasattr(self, "pill") and self.pill:
                self.pill.stop()
        except Exception:
            pass

        # 2. Stop tray icon
        try:
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass

        # 3. Schedule UI destruction on main thread
        try:
            if hasattr(self, "dashboard") and self.dashboard and self.dashboard.root:
                self.dashboard.root.after(0, self._destroy_ui_and_exit)
        except Exception:
            pass

        # 4. Fallback exit watchdog (0.35s) to guarantee zero orphaned background threads
        def force_watchdog():
            time.sleep(0.35)
            self._cleanup_resources()
            os._exit(0)
        threading.Thread(target=force_watchdog, daemon=True).start()

    def _destroy_ui_and_exit(self):
        """Main UI thread handler to cleanly close all Win32 windows."""
        try:
            if hasattr(self, "pill") and self.pill:
                self.pill.stop()
        except Exception:
            pass
        try:
            if hasattr(self, "dashboard") and self.dashboard and self.dashboard.root:
                self.dashboard.root.withdraw()
                self.dashboard.root.destroy()
                self.dashboard.root.quit()
        except Exception:
            pass
        self._cleanup_resources()
        os._exit(0)

    def _cleanup_resources(self):
        """Release audio hardware and tray icon."""
        try:
            if hasattr(self, "tray_icon") and self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass
        try:
            if hasattr(self, "pill") and self.pill:
                self.pill.stop()
        except Exception:
            pass
        try:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
            self.audio.terminate()
        except Exception:
            pass

    def run(self):
        """Main UI thread execution loop."""
        try:
            self.dashboard.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup_resources()
            os._exit(0)


if __name__ == "__main__":
    # Check if Jarvis is already running; if so, open dashboard and exit cleanly
    if check_single_instance(IPC_PORT):
        print("[OK] Jarvis is already running in background. Sent signal to open dashboard.")
        sys.exit(0)

    # First instance: run full background agent
    agent = FastAgent()
    agent.run()
