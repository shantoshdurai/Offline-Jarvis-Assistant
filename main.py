import os
import sys
import queue
import time
import subprocess
import threading
import numpy as np
import sounddevice as sd
import pyaudio
import pygame
import winsound
import ctypes
import pystray
from PIL import Image, ImageDraw
import site

# Ensure CUDA dlls (cublas, cudnn) can be loaded for GPU-accelerated Whisper
for s in site.getsitepackages() + [r"C:\Users\Dog\AppData\Local\Programs\Python\Python311\Lib\site-packages"]:
    candidate = os.path.join(s, "torch", "lib")
    if os.path.exists(candidate) and candidate not in os.environ.get("PATH", ""):
        os.environ["PATH"] = candidate + os.pathsep + os.environ["PATH"]
        if hasattr(os, "add_dll_directory"):
            try: os.add_dll_directory(candidate)
            except Exception: pass

import ctranslate2
from openwakeword.model import Model
from faster_whisper import WhisperModel
from llama_cpp import Llama

# Configurations
WAKE_WORD = "jarvis"  # We will use openwakeword's built-in models

# Automatically detect best model in models/
MODEL_PATH = "models/gemma-3-270m-it-Q4_K_M.gguf"
if os.path.exists("models"):
    candidates = [f for f in os.listdir("models") if f.endswith(".gguf")]
    if candidates:
        candidates.sort(key=lambda f: (
            "coder" in f.lower(),
            "qwen" in f.lower(),
            "llama" in f.lower(),
            os.path.getsize(os.path.join("models", f))
        ), reverse=True)
        MODEL_PATH = os.path.join("models", candidates[0])

import re
import tools

SYSTEM_PROMPT = """You are Jarvis, an offline personal AI assistant and DSA coding mentor running 100% locally on Shantosh's laptop.
You are powered by Qwen 2.5 Coder. You are NOT developed by OpenAI, NOT GPT-4, and NOT Gemini. Always identify yourself as Jarvis.

VOICE & RESPONSE STYLE:
- Your words are spoken aloud through text-to-speech. Never speak raw programming syntax, punctuation, or code lines.
- When explaining an algorithm or concept, explain the intuition simply in 2-3 sentences.
- Place actual code implementation cleanly in ```python ... ``` blocks.
- Be an interactive pair programmer: offer hints, ask if the user wants the problem opened on LeetCode, or ask if they want to try it first.

AVAILABLE TOOLS:
You have real tools to control the computer. When asked to open something or perform an action, use the exact format on its own line:
- Open website or search: <<TOOL: open_url("https://youtube.com", browser="firefox")>>
- Open LeetCode problem: <<TOOL: open_leetcode("valid-parentheses")>>
- Open local application: <<TOOL: open_app("firefox")>> (or "code", "notepad", "terminal", "chrome", "calc")
- Take screenshot: <<TOOL: take_screenshot()>>
- Open folder: <<TOOL: open_folder("C:/Users/Dog/Downloads")>>
- Move file or folder: <<TOOL: move_item("source_path", "destination_path")>>
- Run terminal command: <<TOOL: run_command("command")>>
Always briefly tell the user what you are opening or doing."""
HISTORY = [{"role": "system", "content": SYSTEM_PROMPT}]

# Initialize Pygame Mixer for Audio Playback
pygame.mixer.init()

print(f"Loading LLM ({os.path.basename(MODEL_PATH)})...")
llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1, # Use all available GPU layers
    n_ctx=4096,
    verbose=False
)

whisper_device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
whisper_compute = "float16" if whisper_device == "cuda" else "int8"
try:
    print(f"Loading Whisper Model (faster-whisper small.en on {whisper_device.upper()})...")
    whisper_model = WhisperModel("small.en", device=whisper_device, compute_type=whisper_compute)
except Exception:
    print("Loading Whisper Model (faster-whisper base.en fallback)...")
    whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")

print("Loading Wake Word Model (openwakeword)...")
owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

# Audio Stream for wake word
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1280

audio = pyaudio.PyAudio()
mic_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

# Threading events
is_processing = threading.Event()
voice_command_queue = queue.Queue()

def clean_for_speech(text):
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
    return re.sub(r'\s+', ' ', t).strip()

def speak(text):
    print(f"\nJarvis: {text}")
    spoken_text = clean_for_speech(text)
    if not spoken_text:
        return
    output_file = "reply.mp3"
    text_file = "reply.txt"
    try:
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(spoken_text)
            
        subprocess.run(["edge-tts", "--voice", "en-GB-RyanNeural", "--rate=+10%", "--volume=+100%", "-f", text_file, "--write-media", output_file], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
    except subprocess.TimeoutExpired:
        print("(TTS Error: Network connection to Microsoft Servers timed out.)")
    except Exception as e:
        print(f"(TTS Error: {e})")

def record_audio(max_duration=20, silence_limit=2.0, start_timeout=5.0):
    print("\n[Listening... Speak now!]")
    winsound.MessageBeep(winsound.MB_ICONASTERISK) # Ding sound
    
    frames = []
    silent_chunks = 0
    chunks_per_second = RATE / CHUNK
    max_silent_chunks = int(silence_limit * chunks_per_second)
    max_total_chunks = int(max_duration * chunks_per_second)
    timeout_chunks = int(start_timeout * chunks_per_second)
    
    talking_started = False
    
    # Flush any old audio from the mic buffer
    while mic_stream.get_read_available() > 0:
        mic_stream.read(mic_stream.get_read_available(), exception_on_overflow=False)

    for i in range(max_total_chunks):
        data = mic_stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        
        # Simple volume detection
        audio_data = np.frombuffer(data, dtype=np.int16)
        volume = np.abs(audio_data).mean()
        
        # Threshold adjusted for laptop mic (noise floor is ~650, speech ~850+)
        if volume > 850: 
            talking_started = True
            silent_chunks = 0
        elif talking_started:
            silent_chunks += 1
            
        if talking_started and silent_chunks > max_silent_chunks:
            break
            
        if not talking_started and i > timeout_chunks:
            break

    import wave
    with wave.open('input.wav', 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        
    winsound.MessageBeep(winsound.MB_OK) # End ding
    return 'input.wav'

def transcribe(audio_file):
    segments, info = whisper_model.transcribe(audio_file, beam_size=5, condition_on_previous_text=False)
    text = "".join([segment.text for segment in segments])
    return text.strip()

def generate_response(user_text):
    global HISTORY
    HISTORY.append({"role": "user", "content": user_text})
    try:
        response = llm.create_chat_completion(
            messages=HISTORY,
            max_tokens=1024,
            temperature=0.6,
            repeat_penalty=1.15,
        )
        reply = response['choices'][0]['message']['content'].strip()
        HISTORY.append({"role": "assistant", "content": reply})

        # Check and execute tools
        found, action_msg, clean_text = tools.parse_and_execute_tool(reply)
        if found and action_msg:
            print(f"\n{action_msg}")
            speak(action_msg.replace("[Action: ", "").replace("]", ""))

        return reply
    except Exception as e:
        return f"Error: {e}"

def wake_word_listener():
    """Background thread that constantly listens for 'Jarvis'"""
    while True:
        try:
            if not is_processing.is_set():
                audio_data = np.frombuffer(mic_stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
                prediction = owwModel.predict(audio_data)
                
                # --- REAL TIME MIC DEBUGGING IN TITLE BAR ---
                vol = int(np.abs(audio_data).mean())
                max_score = max(prediction.values()) if prediction else 0.0
                title = f"Jarvis AI | Mic Vol: {vol} | Hey Jarvis Score: {max_score:.3f}"
                ctypes.windll.kernel32.SetConsoleTitleW(title)
                # --------------------------------------------
                
                # Dynamically check the score of the loaded model
                # Lowered from 0.4 to 0.25 to make it super easy to wake up
                if max_score > 0.25:
                    # Wake word detected! Trigger processing state
                    is_processing.set()
                    voice_command_queue.put(True)
                    owwModel.reset()
            else:
                time.sleep(0.1) # Idle while processing
        except OSError:
            break # The stream was intentionally closed during shutdown
        except Exception as e:
            print(f"\n[Wake Word Error: {e}]")
            time.sleep(1)

# System Tray Logic
def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), "black")
    dc = ImageDraw.Draw(image)
    dc.ellipse((16, 16, 48, 48), fill="cyan")
    return image

def hide_console(icon=None, item=None):
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)

def show_console(icon=None, item=None):
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 5)

def quit_app(icon, item):
    icon.stop()
    os._exit(0)

def setup_tray():
    menu = pystray.Menu(
        pystray.MenuItem('Show Terminal', show_console),
        pystray.MenuItem('Hide Terminal', hide_console),
        pystray.MenuItem('Quit Jarvis', quit_app)
    )
    icon = pystray.Icon("Jarvis", create_image(), "Jarvis AI", menu)
    hide_console() # Automatically hide when started
    icon.run()

def run_assistant():
    # Start System Tray icon
    tray_thread = threading.Thread(target=setup_tray, daemon=True)
    tray_thread.start()

    # Play a welcoming startup sound
    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
    winsound.PlaySound("SystemHand", winsound.SND_ALIAS)
    
    print("\n=======================================================")
    print(" Jarvis is Online. ")
    print(" - Say 'Jarvis' to wake me up.")
    print(" - Or type your message below and press Enter.")
    print("=======================================================\n")
    
    speak("Jarvis is online and ready for your command.")
    
    # Start wake word listener thread
    listener_thread = threading.Thread(target=wake_word_listener, daemon=True)
    listener_thread.start()
    
    while True:
        try:
            # We use a non-blocking way to check for both keyboard input and voice commands
            print("\nYou: ", end="", flush=True)
            user_text = ""
            
            # Wait for either a voice trigger or a keyboard enter
            while True:
                # Check if voice triggered
                if not voice_command_queue.empty():
                    voice_command_queue.get()
                    audio_file = record_audio(duration=5)
                    print("\n[Transcribing...]")
                    user_text = transcribe(audio_file)
                    print(f"You (Voice): {user_text}")
                    break
                
                # We use a quick timeout trick on Windows for non-blocking input
                import msvcrt
                if msvcrt.kbhit():
                    char = msvcrt.getwche()
                    if char == '\r' or char == '\n': # Enter key
                        is_processing.set() # Block wake word
                        break
                    elif char == '\b': # Backspace
                        user_text = user_text[:-1]
                        print(" \b", end="", flush=True)
                    else:
                        user_text += char
                time.sleep(0.05)
            
            if user_text.strip():
                print("\n[Jarvis is thinking...]")
                reply = generate_response(user_text)
                speak(reply)
            
            # Resume listening
            is_processing.clear()
            
        except KeyboardInterrupt:
            print("\nShutting down Jarvis...")
            break

if __name__ == "__main__":
    try:
        run_assistant()
    finally:
        mic_stream.stop_stream()
        mic_stream.close()
        audio.terminate()
