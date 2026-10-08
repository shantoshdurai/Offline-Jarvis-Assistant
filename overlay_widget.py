"""OpenWhispr-Style Floating Voice Pill Overlay Widget.

Features:
- Frameless, always-on-top, transparent rounded floating capsule
- States:
  - "idle": Subtle compact 40x40 orb or hidden
  - "recording": 110x38 pill with mic icon + live-level animated waveform equalizer bars
  - "processing": 40x40 circle with glowing cyan/blue rotating spinner arc
  - "speaking": Soft glowing cyan ring
- OpenWhispr exact synthesized harmonic audio cues (C5->E5 start, D5->A4 stop)
"""

import time
import math
import threading
import queue
import tkinter as tk
import numpy as np
import pygame
import io
import wave

# Sound Synthesis matching OpenWhispr dictationCues.js
def _generate_tone(freq: float, duration: float = 0.09, attack: float = 0.015, sr: int = 44100, max_gain: float = 0.2) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave_data = np.sin(2 * np.pi * freq * t)
    n_attack = int(sr * attack)
    env = np.zeros_like(wave_data)
    env[:n_attack] = np.linspace(0.001, max_gain, n_attack)
    env[n_attack:] = max_gain * np.exp(-4.5 * np.linspace(0, 1, len(wave_data) - n_attack))
    return wave_data * env

def _make_sound_cue(notes: list, sr: int = 44100):
    gap = np.zeros(int(sr * 0.025))
    tones = []
    for f in notes:
        tones.append(_generate_tone(f, sr=sr))
        tones.append(gap)
    audio = (np.concatenate(tones) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())
    buf.seek(0)
    return pygame.mixer.Sound(buf)


class FloatingVoicePill:
    def __init__(self):
        self.state = "idle"  # idle, recording, processing, speaking
        self.current_level = 0.0
        self.target_level = 0.0
        self.spin_angle = 0
        self.is_running = True
        self.queue = queue.Queue()

        # Initialize Pygame Mixer for sound cues
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.start_cue = _make_sound_cue([523.25, 659.25])  # C5 -> E5 (OpenWhispr start)
            self.stop_cue = _make_sound_cue([587.33, 440.0])   # D5 -> A4 (OpenWhispr stop)
        except Exception:
            self.start_cue = None
            self.stop_cue = None

        # Start Tkinter thread
        self.thread = threading.Thread(target=self._run_tk, daemon=True)
        self.thread.start()

    def play_sfx(self, cue_type: str = "start"):
        """Play OpenWhispr harmonic chime."""
        try:
            if cue_type == "start" and self.start_cue:
                self.start_cue.play()
            elif cue_type in ("stop", "end") and self.stop_cue:
                self.stop_cue.play()
        except Exception:
            pass

    def set_state(self, state: str):
        """Set widget state: 'idle', 'recording', 'processing', 'speaking'."""
        self.state = state
        self.queue.put(("state", state))
        if state == "recording":
            self.play_sfx("start")
        elif state in ("processing", "idle"):
            self.play_sfx("stop")

    def update_volume(self, vol: float):
        """Update live audio level (0.0 to 1.0)."""
        self.target_level = max(0.0, min(1.0, vol))

    def _run_tk(self):
        self.root = tk.Tk()
        self.root.title("Jarvis Voice Pill")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # Transparent background key on Windows
        TRANS_COLOR = "#010101"
        self.root.configure(bg=TRANS_COLOR)
        self.root.attributes("-transparentcolor", TRANS_COLOR)

        # Screen dimensions
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        self.w_idle = 44
        self.w_rec = 114
        self.h = 42

        # Position at bottom-right just above Windows taskbar tray
        self.pos_x = screen_w - self.w_rec - 30
        self.pos_y = screen_h - self.h - 60

        self.root.geometry(f"{self.w_rec}x{self.h}+{self.pos_x}+{self.pos_y}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.w_rec,
            height=self.h,
            bg=TRANS_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Make widget draggable
        def start_drag(event):
            self._drag_start_x = event.x
            self._drag_start_y = event.y

        def do_drag(event):
            x = self.root.winfo_x() + (event.x - self._drag_start_x)
            y = self.root.winfo_y() + (event.y - self._drag_start_y)
            self.root.geometry(f"+{x}+{y}")

        self.canvas.bind("<Button-1>", start_drag)
        self.canvas.bind("<B1-Motion>", do_drag)

        # Start animation ticker
        self._animate()
        self.root.mainloop()

    def _draw_pill_bg(self, w, h, fill="#18181b", outline="#27272a"):
        r = (h - 2) / 2
        # Left circle
        self.canvas.create_oval(2, 2, 2 + 2*r, h - 2, fill=fill, outline=outline, width=1.5)
        # Right circle
        self.canvas.create_oval(w - 2 - 2*r, 2, w - 2, h - 2, fill=fill, outline=outline, width=1.5)
        # Middle rectangle
        self.canvas.create_rectangle(2 + r, 2, w - 2 - r, h - 2, fill=fill, outline=fill)
        # Top and bottom border lines
        self.canvas.create_line(2 + r, 2, w - 2 - r, 2, fill=outline, width=1.5)
        self.canvas.create_line(2 + r, h - 2, w - 2 - r, h - 2, fill=outline, width=1.5)

    def _draw_mic_icon(self, cx, cy):
        # White circular mic badge
        r_outer = 13
        self.canvas.create_oval(cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer, outline="#ffffff", width=1.5)
        # Inner vertical sound bars inside circle
        self.canvas.create_line(cx - 4, cy - 4, cx - 4, cy + 4, fill="#ffffff", width=1.5)
        self.canvas.create_line(cx, cy - 7, cx, cy + 7, fill="#ffffff", width=2)
        self.canvas.create_line(cx + 4, cy - 4, cx + 4, cy + 4, fill="#ffffff", width=1.5)

    def _animate(self):
        # Process any pending events
        while not self.queue.empty():
            msg, val = self.queue.get_nowait()
            if msg == "state":
                self.state = val

        self.canvas.delete("all")
        self.current_level += (self.target_level - self.current_level) * 0.35

        if self.state == "recording":
            # Expand to 110px pill with animated waveform
            w = self.w_rec
            self._draw_pill_bg(w, self.h, fill="#16161a", outline="#2e2e38")
            self._draw_mic_icon(20, self.h / 2)

            # Draw 8 animated waveform equalizer bars
            num_bars = 8
            start_x = 42
            bar_gap = 7
            max_bar_h = 22
            min_bar_h = 4
            mid_y = self.h / 2

            t_ms = time.time() * 10
            for i in range(num_bars):
                bx = start_x + i * bar_gap
                # Smooth sinusoidal variation driven by volume level
                wave_factor = 0.5 + 0.5 * math.sin(t_ms + i * 0.8)
                bar_h = min_bar_h + (max_bar_h - min_bar_h) * self.current_level * wave_factor
                self.canvas.create_line(
                    bx, mid_y - bar_h / 2,
                    bx, mid_y + bar_h / 2,
                    fill="#f4f4f5",
                    width=2.5,
                    capstyle="round"
                )

        elif self.state == "processing":
            # Circular 40x40 orb with rotating cyan spinner ring
            w = self.w_idle
            cx, cy = w / 2, self.h / 2
            r = 18
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#18181b", outline="#27272a", width=1.5)
            self._draw_mic_icon(cx, cy)

            # Rotating glowing cyan arc
            self.spin_angle = (self.spin_angle + 14) % 360
            self.canvas.create_arc(
                cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1,
                start=self.spin_angle,
                extent=100,
                outline="#00dcff",
                width=2.5,
                style="arc"
            )

        elif self.state == "speaking":
            # Glowing cyan/green pulsing orb
            w = self.w_idle
            cx, cy = w / 2, self.h / 2
            r = 18
            pulse = 1.0 + 0.15 * math.sin(time.time() * 8)
            self.canvas.create_oval(cx - r*pulse, cy - r*pulse, cx + r*pulse, cy + r*pulse, fill="#18181b", outline="#00e676", width=2)
            self._draw_mic_icon(cx, cy)

        else: # idle
            # Subtle dark orb
            w = self.w_idle
            cx, cy = w / 2, self.h / 2
            r = 17
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#121215", outline="#222226", width=1.5)
            self._draw_mic_icon(cx, cy)

        # Loop at ~35 FPS for buttery smooth animation
        self.root.after(28, self._animate)
