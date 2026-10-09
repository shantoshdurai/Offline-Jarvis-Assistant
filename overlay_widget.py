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
import collections
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
    def __init__(self, parent=None):
        self.parent = parent
        self.state = "idle"  # idle, recording, processing, speaking, listening
        self.current_level = 0.0
        self.target_level = 0.0
        self.spin_angle = 0
        self.is_running = True
        self.queue = queue.Queue()

        # OpenWhispr authentic 11-bar equalizer state
        self.bar_history = collections.deque([0.0] * 11, maxlen=11)
        self.displayed_bars = [0.0] * 11
        self._last_bar_shift = time.time()

        # Initialize Pygame Mixer for sound cues
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.start_cue = _make_sound_cue([523.25, 659.25])  # C5 -> E5 (OpenWhispr start)
            self.stop_cue = _make_sound_cue([587.33, 440.0])   # D5 -> A4 (OpenWhispr stop)
        except Exception:
            self.start_cue = None
            self.stop_cue = None

        self._is_visible = False
        self._last_active_time = 0.0

        if self.parent is not None:
            self._init_ui(self.parent)
        else:
            # Start Tkinter thread
            self.thread = threading.Thread(target=self._run_tk, daemon=True)
            self.thread.start()

        self.sfx_enabled = True

    def play_sfx(self, cue_type: str = "wake"):
        """Play OpenWhispr harmonic chime (wake: C5->E5, sleep: D5->A4)."""
        if not self.sfx_enabled:
            return
        try:
            if cue_type in ("wake", "start") and self.start_cue:
                self.start_cue.play()
            elif cue_type in ("sleep", "stop", "end") and self.stop_cue:
                self.stop_cue.play()
        except Exception:
            pass

    def set_state(self, state: str):
        """Set widget state: 'idle', 'recording', 'listening', 'processing', 'speaking'."""
        self.state = state
        self.queue.put(("state", state))

    def update_volume(self, vol: float):
        """Update live audio level (0.0 to 1.0)."""
        self.target_level = max(0.0, min(1.0, vol))

    def stop(self):
        """Cleanly destroy overlay widget immediately."""
        self.is_running = False
        self.queue.put(("destroy", None))

    def _init_ui(self, parent_widget):
        if parent_widget is not None:
            self.root = tk.Toplevel(parent_widget)
        else:
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

        # Start hidden by default
        self.root.withdraw()
        self._is_visible = False

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

    def _run_tk(self):
        self._init_ui(None)
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

    def _draw_mic_icon(self, cx, cy, color="#ffffff"):
        # Circular mic badge
        r_outer = 13
        self.canvas.create_oval(cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer, outline=color, width=1.5)
        # Inner vertical sound bars inside circle
        self.canvas.create_line(cx - 4, cy - 4, cx - 4, cy + 4, fill=color, width=1.5)
        self.canvas.create_line(cx, cy - 7, cx, cy + 7, fill=color, width=2)
        self.canvas.create_line(cx + 4, cy - 4, cx + 4, cy + 4, fill=color, width=1.5)

    def _animate(self):
        if not self.is_running:
            try:
                self.root.withdraw()
                self.root.destroy()
            except Exception:
                pass
            return

        # Process any pending events
        while not self.queue.empty():
            msg, val = self.queue.get_nowait()
            if msg == "state":
                self.state = val
            elif msg == "destroy":
                try:
                    self.root.quit()
                    self.root.destroy()
                except Exception:
                    pass
                return


        now = time.time()
        # Manage auto-show and auto-hide
        if self.state in ("recording", "processing", "speaking", "listening"):
            if not self._is_visible:
                self.root.deiconify()
                self._is_visible = True
            self._last_active_time = now
        else:
            if self._is_visible:
                if now - self._last_active_time > 0.4:
                    self.root.withdraw()
                    self._is_visible = False

        self.canvas.delete("all")
        self.current_level += (self.target_level - self.current_level) * 0.4

        # Shift audio levels through the 11 equalizer history slots every ~75ms (OpenWhispr $s = 80ms)
        if now - self._last_bar_shift >= 0.075:
            self._last_bar_shift = now
            push_val = self.current_level if self.current_level >= 0.02 else 0.0
            self.bar_history.append(push_val)

        # Smoothly interpolate each displayed bar height towards target
        for i in range(11):
            target_b = self.bar_history[i]
            self.displayed_bars[i] += (target_b - self.displayed_bars[i]) * 0.35

        w = self.w_rec
        mid_y = self.h / 2
        start_x = 42
        end_x = 102
        step = (end_x - start_x) / 10  # 6.0px per bar

        if self.state in ("recording", "listening", "speaking"):
            if self.state == "speaking":
                outline_col = "#10b981"
                icon_col = "#10b981"
                bar_col = "#10b981"
                silent_col = "#047857"
            elif self.state == "recording":
                outline_col = "#38bdf8"
                icon_col = "#ffffff"
                bar_col = "#38bdf8"
                silent_col = "#64748b"
            else:  # listening
                outline_col = "#0ea5e9"
                icon_col = "#ffffff"
                bar_col = "#0ea5e9"
                silent_col = "#64748b"

            self._draw_pill_bg(w, self.h, fill="#16161a", outline=outline_col)
            self._draw_mic_icon(20, mid_y, color=icon_col)

            # Draw the 11 OpenWhispr equalizer bars (4px resting height when silent, dynamic to 22px when speaking)
            for i in range(11):
                bx = start_x + i * step
                lvl = max(0.0, min(1.0, self.displayed_bars[i]))
                if lvl < 0.02:
                    bar_h = 4.0
                    col = silent_col
                else:
                    zs = min(1.0, (lvl * 8.0) ** 0.75)
                    bar_h = 4.0 + zs * 18.0
                    col = bar_col

                y_top = mid_y - bar_h / 2.0
                y_bot = mid_y + bar_h / 2.0
                self.canvas.create_line(
                    bx, y_top, bx, y_bot,
                    fill=col,
                    width=2.5,
                    capstyle="round"
                )

        elif self.state == "processing":
            # Thinking / generating state: Pill stays expanded at 114px with high-tech glowing wave across the 11 bars
            outline_col = "#00e5ff"
            self._draw_pill_bg(w, self.h, fill="#16161a", outline=outline_col)
            self._draw_mic_icon(20, mid_y, color="#00e5ff")

            # Sweeping shimmer pulse across 11 bars
            t_wave = now * 7.5
            for i in range(11):
                bx = start_x + i * step
                phase = math.sin(t_wave - i * 0.55)
                bar_h = 5.0 + 11.0 * (0.5 + 0.5 * phase)
                y_top = mid_y - bar_h / 2.0
                y_bot = mid_y + bar_h / 2.0
                self.canvas.create_line(
                    bx, y_top, bx, y_bot,
                    fill="#00e5ff",
                    width=2.5,
                    capstyle="round"
                )

        else: # idle
            # Subtle dark resting circle
            w_idle = self.w_idle
            cx, cy = w_idle / 2, mid_y
            r = 17
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#121215", outline="#222226", width=1.5)
            self._draw_mic_icon(cx, cy, color="#475569")

        # Loop at ~35 FPS for buttery smooth animation
        self.root.after(28, self._animate)

