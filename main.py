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
from openwakeword.model import Model
from faster_whisper import WhisperModel
from llama_cpp import Llama

# Configurations
WAKE_WORD = "jarvis"  # We will use openwakeword's built-in models
MODEL_PATH = "models/gemma-3-270m-it-Q4_K_M.gguf"
SYSTEM_PROMPT = "You are Jarvis, a helpful and concise AI assistant. Keep your answers brief and conversational."

# Initialize Pygame Mixer for Audio Playback
pygame.mixer.init()

print("Loading LLM (Gemma 3 270M)...")
llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1, # Use all available GPU layers
    n_ctx=2048,
    verbose=False
)

print("Loading Whisper Model (faster-whisper base.en)...")
whisper_model = WhisperModel("base.en", device="cuda", compute_type="float16")

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

def speak(text):
    print(f"\nJarvis: {text}")
    output_file = "reply.mp3"
    text_file = "reply.txt"
    try:
        # Write to file to completely bypass Windows command-line escaping bugs with special characters
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(text)
            
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

def record_audio(max_duration=15, silence_limit=1.2, start_timeout=3.0):
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
        
        # Threshold adjusted for your hardware (your noise floor is ~1000)
        if volume > 2000: 
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
    segments, info = whisper_model.transcribe(audio_file, beam_size=5)
    text = "".join([segment.text for segment in segments])
    return text.strip()

def generate_response(user_text):
    prompt = f"<start_of_turn>system\n{SYSTEM_PROMPT}<end_of_turn>\n<start_of_turn>user\n{user_text}<end_of_turn>\n<start_of_turn>model\n"
    output = llm(prompt, max_tokens=150, stop=["<end_of_turn>", "<start_of_turn>"], echo=False)
    return output['choices'][0]['text'].strip()

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
