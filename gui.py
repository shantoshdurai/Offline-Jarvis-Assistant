import os
import time
import threading
import queue
import numpy as np
import pyaudio
import wave
import customtkinter as ctk
import subprocess
import sys
from llama_cpp import Llama
from faster_whisper import WhisperModel
from openwakeword.model import Model

# Prevent crashes in PyInstaller Windowed mode when background libraries try to print
class DummyFile:
    def write(self, x): pass
    def flush(self): pass
if getattr(sys, 'frozen', False):
    sys.stdout = DummyFile()
    sys.stderr = DummyFile()

# --- CONFIGURATION ---
SYSTEM_PROMPT = "You are Jarvis, a highly intelligent AI assistant. Keep responses under 2 sentences unless asked for details."
HISTORY = [{"role": "system", "content": SYSTEM_PROMPT}]
is_processing = threading.Event()
voice_command_queue = queue.Queue()

class JarvisGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Jarvis AI Assistant")
        self.geometry("900x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.is_awake = False
        
        # --- UI ELEMENTS ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.chat_box = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 14), wrap="word")
        self.chat_box.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
        
        self.status_label = ctk.CTkLabel(self, text="Status: Booting AI Models...", text_color="yellow", font=("Arial", 16, "bold"))
        self.status_label.grid(row=1, column=0, pady=(0, 10))
        
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type a message or say 'Hey Jarvis'...", font=("Arial", 14))
        self.entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.entry.bind("<Return>", self.send_text)
        
        self.send_btn = ctk.CTkButton(self.input_frame, text="Send", command=self.send_text, width=80)
        self.send_btn.grid(row=0, column=1)
        
        # Models and Audio
        self.llm = None
        self.whisper_model = None
        self.owwModel = None
        self.audio = None
        self.mic_stream = None
        
        # Start Loading Thread
        threading.Thread(target=self.load_models, daemon=True).start()

    def update_chat(self, sender, text, color="white"):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"[{sender}]\n{text}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")
        
    def set_status(self, text, color="white"):
        self.status_label.configure(text=f"Status: {text}", text_color=color)

    def speak_text(self, text):
        clean_text = text.replace("'", "").replace('"', "")
        script = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Rate = 1; $synth.Speak('{clean_text}')"
        subprocess.run(["powershell", "-Command", script], creationflags=subprocess.CREATE_NO_WINDOW)

    def load_models(self):
        try:
            self.update_chat("System", "Loading LLM (Gemma 3 270M)...", "gray")
            self.llm = Llama(model_path="models/gemma-3-270m-it-Q4_K_M.gguf", n_ctx=2048, verbose=False)
            
            self.update_chat("System", "Loading Whisper (Ears)...", "gray")
            self.whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
            
            self.update_chat("System", "Loading OpenWakeWord...", "gray")
            self.owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            
            self.update_chat("System", "All models loaded! Jarvis is online.", "green")
            self.set_status("Listening for 'Hey Jarvis'...", "lightgreen")
            
            # Start Audio
            self.start_audio()
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
        while True:
            try:
                if not is_processing.is_set():
                    data = self.mic_stream.read(self.CHUNK, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    prediction = self.owwModel.predict(audio_data)
                    max_score = max(prediction.values()) if prediction else 0.0
                    
                    if max_score > 0.25:
                        is_processing.set()
                        voice_command_queue.put(True)
                        self.owwModel.reset()
                else:
                    time.sleep(0.1)
            except OSError:
                break
            except Exception:
                time.sleep(1)

    def process_queue(self):
        while True:
            if not voice_command_queue.empty():
                voice_command_queue.get()
                self.is_awake = True
                while self.is_awake:
                    self.handle_voice_interaction()
            time.sleep(0.1)

    def handle_voice_interaction(self):
        self.set_status("Listening... Speak now!", "orange")
        
        frames = []
        silent_chunks = 0
        chunks_per_second = self.RATE / self.CHUNK
        max_silent_chunks = int(1.2 * chunks_per_second)
        max_total_chunks = int(15 * chunks_per_second)
        timeout_chunks = int(3.0 * chunks_per_second)
        talking_started = False
        
        # Flush buffer
        while self.mic_stream.get_read_available() > 0:
            self.mic_stream.read(self.mic_stream.get_read_available(), exception_on_overflow=False)
            
        for i in range(max_total_chunks):
            data = self.mic_stream.read(self.CHUNK, exception_on_overflow=False)
            frames.append(data)
            
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_data).mean()
            
            if volume > 2000: 
                talking_started = True
                silent_chunks = 0
            elif talking_started:
                silent_chunks += 1
                
            if talking_started and silent_chunks > max_silent_chunks:
                break
            if not talking_started and i > timeout_chunks:
                break
                
        with wave.open('input.wav', 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames))
            
        self.set_status("Transcribing...", "yellow")
        try:
            segments, _ = self.whisper_model.transcribe("input.wav", beam_size=5)
            user_text = "".join(segment.text for segment in segments).strip()
            
            if user_text:
                lower_text = user_text.lower()
                if "bye" in lower_text or "terminate" in lower_text:
                    self.update_chat("You", user_text, "white")
                    self.update_chat("Jarvis", "Goodbye! Going back to sleep.", "yellow")
                    self.set_status("Jarvis is speaking...", "orange")
                    self.speak_text("Goodbye! Going back to sleep.")
                    self.is_awake = False
                    self.set_status("Listening for 'Hey Jarvis'...", "lightgreen")
                    is_processing.clear()
                else:
                    self.process_user_input(user_text)
            else:
                self.is_awake = False
                self.set_status("Listening for 'Hey Jarvis'...", "lightgreen")
                is_processing.clear()
        except Exception as e:
            self.is_awake = False
            self.set_status("Listening for 'Hey Jarvis'...", "lightgreen")
            is_processing.clear()

    def send_text(self, event=None):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, 'end')
            is_processing.set()
            threading.Thread(target=self.process_user_input, args=(text,), daemon=True).start()

    def process_user_input(self, text):
        self.update_chat("You", text, "white")
        self.set_status("Jarvis is thinking...", "yellow")
        
        HISTORY.append({"role": "user", "content": text})
        
        try:
            response = self.llm.create_chat_completion(
                messages=HISTORY,
                max_tokens=150,
                temperature=0.7,
            )
            reply = response['choices'][0]['message']['content'].strip()
            HISTORY.append({"role": "assistant", "content": reply})
            
            self.update_chat("Jarvis", reply, "yellow")
            self.set_status("Jarvis is speaking...", "orange")
            
            self.speak_text(reply)
            
        except Exception as e:
            self.update_chat("Error", str(e), "red")
            
        if not self.is_awake:
            self.set_status("Listening for 'Hey Jarvis'...", "lightgreen")
            is_processing.clear()

if __name__ == "__main__":
    app = JarvisGUI()
    app.mainloop()
