"""Jarvis AI - Modern Desktop Dashboard GUI.

Inspired by OpenWhispr's dark minimalist desktop interface:
- Deep obsidian dark theme (#0e0f13 / #13141b / #171821)
- Left navigation sidebar:
    - Logo & Title with live glowing status pill
    - Home (Feed of recent voice transcripts & executed actions)
    - Chat (Direct interactive conversation)
    - Quick Tools (YouTube player, app launcher, volume controls)
    - Settings (Hotkeys, wake word toggle, OpenRouter API key)
    - "Stop Jarvis" button (clean 1-click complete shutdown)
- Header with push-to-talk trigger button
- Activity cards grouped by date/time (Today, Yesterday, etc.)
- Minimize-to-tray on close ('X' button hides window without killing background engine)
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List

import customtkinter as ctk

# Configure theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")


def load_history() -> List[Dict[str, Any]]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history: List[Dict[str, Any]]):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "follow_up_timeout": 10.0,
    "silence_limit": 0.55,
    "sfx_enabled": True,
    "voice_dismissal_enabled": True,
    "wake_word_enabled": True,
}


def load_config() -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


class JarvisDashboard:
    def __init__(
        self,
        on_trigger_voice: Optional[Callable[[], None]] = None,
        on_send_chat: Optional[Callable[[str], None]] = None,
        on_stop_jarvis: Optional[Callable[[], None]] = None,
        on_save_api_key: Optional[Callable[[str], None]] = None,
        on_toggle_wake_word: Optional[Callable[[bool], None]] = None,
        on_update_settings: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.on_trigger_voice = on_trigger_voice
        self.on_send_chat = on_send_chat
        self.on_stop_jarvis = on_stop_jarvis
        self.on_save_api_key = on_save_api_key
        self.on_toggle_wake_word = on_toggle_wake_word
        self.on_update_settings = on_update_settings

        self.config = load_config()
        self.history = load_history()
        self.current_view = "home"

        # Main Root Window
        self.root = ctk.CTk()
        self.root.title("Jarvis AI — Voice Copilot")
        self.root.geometry("980x640")
        self.root.minsize(860, 520)
        self.root.configure(fg_color="#0e0f13")

        # Set Window Icon if available
        ico_path = os.path.join(BASE_DIR, "jarvis_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        # Intercept window close (minimize to tray instead of quitting)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Build UI Layout
        self._build_layout()

        # Start hidden by default (silent startup)
        self.root.withdraw()

    def _build_layout(self):
        # Top Grid: Sidebar (col 0), Main View (col 1)
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ==========================================
        # LEFT NAVIGATION SIDEBAR
        # ==========================================
        self.sidebar = ctk.CTkFrame(
            self.root,
            width=210,
            corner_radius=0,
            fg_color="#12131a",
            border_width=1,
            border_color="#1c1e28"
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)  # Spacer push to bottom

        # App Brand Header
        self.brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.brand_frame.grid(row=0, column=0, padx=18, pady=(20, 16), sticky="w")

        self.logo_badge = ctk.CTkLabel(
            self.brand_frame,
            text="⚡",
            font=ctk.CTkFont(size=20),
            text_color="#38bdf8",
            width=32,
            height=32,
            fg_color="#1e293b",
            corner_radius=8
        )
        self.logo_badge.pack(side="left", padx=(0, 10))

        self.title_box = ctk.CTkFrame(self.brand_frame, fg_color="transparent")
        self.title_box.pack(side="left")

        self.title_label = ctk.CTkLabel(
            self.title_box,
            text="Jarvis AI",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#f8fafc"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            self.title_box,
            text="Fast Voice Copilot",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.subtitle_label.pack(anchor="w")

        # Status Pill (Active • Listening)
        self.status_pill = ctk.CTkFrame(
            self.sidebar,
            fg_color="#064e3b",
            corner_radius=12,
            height=26
        )
        self.status_pill.grid(row=1, column=0, padx=18, pady=(0, 20), sticky="ew")

        self.status_dot = ctk.CTkLabel(
            self.status_pill,
            text="●",
            font=ctk.CTkFont(size=12),
            text_color="#10b981",
            width=16
        )
        self.status_dot.pack(side="left", padx=(10, 4))

        self.status_text = ctk.CTkLabel(
            self.status_pill,
            text="Engine Online • Ready",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#d1fae5"
        )
        self.status_text.pack(side="left", padx=(0, 10))

        # Nav Buttons
        self.nav_home = self._create_nav_btn(
            row=2,
            text="🏠  Home Feed",
            command=lambda: self.show_view("home")
        )
        self.nav_chat = self._create_nav_btn(
            row=3,
            text="💬  Chat",
            command=lambda: self.show_view("chat")
        )
        self.nav_tools = self._create_nav_btn(
            row=4,
            text="⚡  Quick Actions",
            command=lambda: self.show_view("tools")
        )
        self.nav_settings = self._create_nav_btn(
            row=5,
            text="⚙️  Settings",
            command=lambda: self.show_view("settings")
        )

        # Bottom Area of Sidebar
        self.bottom_sidebar = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.bottom_sidebar.grid(row=7, column=0, padx=14, pady=16, sticky="ew")

        # Stop Jarvis Button (Clean red 1-click shutdown)
        self.stop_btn = ctk.CTkButton(
            self.bottom_sidebar,
            text="🛑  Stop Jarvis",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            text_color="#fecaca",
            height=34,
            corner_radius=8,
            command=self._handle_stop_click
        )
        self.stop_btn.pack(fill="x", pady=(0, 6))

        self.hint_label = ctk.CTkLabel(
            self.bottom_sidebar,
            text="'X' minimizes to tray",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        )
        self.hint_label.pack()

        # ==========================================
        # MAIN CONTENT AREA (Header + View container)
        # ==========================================
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=16)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Top Header Bar
        self.header = ctk.CTkFrame(self.main_container, fg_color="transparent", height=42)
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.header.grid_columnconfigure(1, weight=1)

        self.header_title = ctk.CTkLabel(
            self.header,
            text="Activity & Transcripts",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color="#f8fafc"
        )
        self.header_title.grid(row=0, column=0, sticky="w")

        # Header Right Controls: Push-to-Talk Button
        self.header_ptt_btn = ctk.CTkButton(
            self.header,
            text="🎙️  Push to Talk (Ctrl+Shift+Space)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            height=34,
            corner_radius=8,
            command=self._handle_voice_click
        )
        self.header_ptt_btn.grid(row=0, column=2, sticky="e", padx=(10, 0))

        # View Containers
        self.views: Dict[str, ctk.CTkFrame] = {}
        self._build_home_view()
        self._build_chat_view()
        self._build_tools_view()
        self._build_settings_view()

        # Initial view selection
        self.show_view("home")

    def _create_nav_btn(self, row: int, text: str, command: Callable) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            text_color="#94a3b8",
            hover_color="#1e293b",
            height=38,
            corner_radius=8,
            command=command
        )
        btn.grid(row=row, column=0, padx=12, pady=3, sticky="ew")
        return btn

    def show_view(self, name: str):
        self.current_view = name
        nav_map = {
            "home": self.nav_home,
            "chat": self.nav_chat,
            "tools": self.nav_tools,
            "settings": self.nav_settings,
        }
        title_map = {
            "home": "Activity & Transcripts",
            "chat": "Live Assistant Chat",
            "tools": "Quick PC Actions",
            "settings": "System Settings",
        }

        # Update Nav button highlights
        for key, btn in nav_map.items():
            if key == name:
                btn.configure(fg_color="#2563eb", text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color="#94a3b8")

        # Update Header Title
        self.header_title.configure(text=title_map.get(name, "Jarvis AI"))

        # Switch views
        for key, frame in self.views.items():
            if key == name:
                frame.grid(row=1, column=0, sticky="nsew")
            else:
                frame.grid_forget()

    # ==========================================
    # VIEW 1: HOME FEED (OpenWhispr Transcripts Style)
    # ==========================================
    def _build_home_view(self):
        home_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["home"] = home_frame
        home_frame.grid_rowconfigure(1, weight=1)
        home_frame.grid_columnconfigure(0, weight=1)

        # Search / Filter Bar
        search_frame = ctk.CTkFrame(home_frame, fg_color="transparent", height=36)
        search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search voice notes and command history...",
            fg_color="#161720",
            border_color="#232532",
            text_color="#f8fafc",
            placeholder_text_color="#64748b",
            height=36,
            corner_radius=8
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_history())

        # Scrollable Feed Container
        self.feed_scroll = ctk.CTkScrollableFrame(
            home_frame,
            fg_color="#101117",
            border_width=1,
            border_color="#1c1d27",
            corner_radius=10
        )
        self.feed_scroll.grid(row=1, column=0, sticky="nsew")
        self.feed_scroll.grid_columnconfigure(0, weight=1)

        self._render_history_feed()

    def _render_history_feed(self, filter_text: str = ""):
        # Clear existing items
        for widget in self.feed_scroll.winfo_children():
            widget.destroy()

        filter_lower = filter_text.strip().lower()
        filtered = [
            item for item in self.history
            if not filter_lower or filter_lower in item.get("user", "").lower() or filter_lower in item.get("response", "").lower()
        ]

        if not filtered:
            empty_card = ctk.CTkFrame(
                self.feed_scroll,
                fg_color="#161720",
                border_width=1,
                border_color="#232532",
                corner_radius=10
            )
            empty_card.pack(fill="x", padx=14, pady=20)

            lbl = ctk.CTkLabel(
                empty_card,
                text="🎙️ No voice activity yet",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#cbd5e1"
            )
            lbl.pack(pady=(16, 4))

            sub = ctk.CTkLabel(
                empty_card,
                text="Press Ctrl+Shift+Space (or Ctrl+Alt+J) or say 'Hey Jarvis' to speak.\nTranscribed commands and tool actions will appear here.",
                font=ctk.CTkFont(size=12),
                text_color="#64748b"
            )
            sub.pack(pady=(0, 16))
            return

        # Render cards in reverse chronological order
        for item in reversed(filtered[-50:]):
            self._render_item_card(item)

    def _render_item_card(self, item: Dict[str, Any]):
        card = ctk.CTkFrame(
            self.feed_scroll,
            fg_color="#161720",
            border_width=1,
            border_color="#232532",
            corner_radius=10
        )
        card.pack(fill="x", padx=10, pady=6)
        card.grid_columnconfigure(1, weight=1)

        # Header Row: Time + Modality Badge + Tool Badge
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(10, 6))

        time_str = item.get("time", "")
        if not time_str:
            time_str = datetime.now().strftime("%I:%M %p")

        time_lbl = ctk.CTkLabel(
            top_row,
            text=time_str,
            font=ctk.CTkFont(size=11),
            text_color="#64748b"
        )
        time_lbl.pack(side="left")

        # Modality badge
        src = item.get("source", "voice")
        is_voice = (src == "voice")
        badge_text = "🎙️ Voice" if is_voice else "⌨️ Typed"
        badge_color = "#0284c7" if is_voice else "#7c3aed"

        badge = ctk.CTkLabel(
            top_row,
            text=badge_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#e0f2fe" if is_voice else "#ede9fe",
            fg_color=badge_color,
            corner_radius=6,
            width=68,
            height=20
        )
        badge.pack(side="left", padx=10)

        # Tool executed badge
        tool = item.get("tool", "")
        if tool:
            tool_lbl = ctk.CTkLabel(
                top_row,
                text=f"⚡ {tool}",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#86efac",
                fg_color="#064e3b",
                corner_radius=6,
                height=20,
                padx=8
            )
            tool_lbl.pack(side="left")

        # User Query
        user_text = item.get("user", "")
        user_lbl = ctk.CTkLabel(
            card,
            text=user_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f1f5f9",
            justify="left",
            anchor="w",
            wraplength=660
        )
        user_lbl.pack(fill="x", padx=14, pady=(2, 4))

        # Jarvis Response
        resp_text = item.get("response", "")
        if resp_text:
            resp_frame = ctk.CTkFrame(card, fg_color="#101117", corner_radius=6)
            resp_frame.pack(fill="x", padx=14, pady=(4, 10))

            resp_lbl = ctk.CTkLabel(
                resp_frame,
                text=f"🤖  {resp_text}",
                font=ctk.CTkFont(size=12),
                text_color="#94a3b8",
                justify="left",
                anchor="w",
                wraplength=640
            )
            resp_lbl.pack(fill="x", padx=10, pady=8)

    def _filter_history(self):
        text = self.search_entry.get()
        self._render_history_feed(filter_text=text)

    def add_interaction(self, user_text: str, response: str, source: str = "voice", tool: str = ""):
        """Add an interaction item dynamically to history and feed."""
        entry = {
            "time": datetime.now().strftime("%I:%M %p"),
            "date": datetime.now().strftime("%b %d, %Y"),
            "source": source,
            "user": user_text,
            "response": response,
            "tool": tool
        }
        self.history.append(entry)
        save_history(self.history)

        def _update():
            self._render_history_feed()
            # Also append to chat message list
            self._append_chat_message("user", user_text)
            self._append_chat_message("assistant", response)

        self.root.after(0, _update)

    # ==========================================
    # VIEW 2: CHAT VIEW
    # ==========================================
    def _build_chat_view(self):
        chat_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["chat"] = chat_frame
        chat_frame.grid_rowconfigure(0, weight=1)
        chat_frame.grid_columnconfigure(0, weight=1)

        # Message Scroll Area
        self.chat_scroll = ctk.CTkScrollableFrame(
            chat_frame,
            fg_color="#101117",
            border_width=1,
            border_color="#1c1d27",
            corner_radius=10
        )
        self.chat_scroll.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.chat_scroll.grid_columnconfigure(0, weight=1)

        # Initial populate from history
        for item in self.history[-20:]:
            self._append_chat_message("user", item.get("user", ""))
            self._append_chat_message("assistant", item.get("response", ""))

        # Bottom Input Bar
        input_bar = ctk.CTkFrame(chat_frame, fg_color="transparent")
        input_bar.grid(row=1, column=0, sticky="ew")
        input_bar.grid_columnconfigure(0, weight=1)

        self.chat_input = ctk.CTkEntry(
            input_bar,
            placeholder_text="Type a message or command for Jarvis...",
            fg_color="#161720",
            border_color="#232532",
            text_color="#f8fafc",
            placeholder_text_color="#64748b",
            height=40,
            corner_radius=8
        )
        self.chat_input.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.chat_input.bind("<Return>", lambda e: self._handle_chat_send())

        self.chat_send_btn = ctk.CTkButton(
            input_bar,
            text="Send",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            width=70,
            height=40,
            corner_radius=8,
            command=self._handle_chat_send
        )
        self.chat_send_btn.grid(row=0, column=1)

    def _append_chat_message(self, role: str, text: str):
        if not text:
            return
        is_user = (role == "user")
        bubble = ctk.CTkFrame(
            self.chat_scroll,
            fg_color="#1e293b" if is_user else "#161720",
            border_width=1,
            border_color="#334155" if is_user else "#232532",
            corner_radius=10
        )
        bubble.pack(
            fill="x",
            padx=(60 if is_user else 10, 10 if is_user else 60),
            pady=4
        )

        prefix = "You: " if is_user else "Jarvis: "
        msg_lbl = ctk.CTkLabel(
            bubble,
            text=f"{prefix}{text}",
            font=ctk.CTkFont(size=12),
            text_color="#f8fafc" if is_user else "#cbd5e1",
            justify="left",
            anchor="w",
            wraplength=600
        )
        msg_lbl.pack(fill="x", padx=12, pady=8)

    def _handle_chat_send(self):
        msg = self.chat_input.get().strip()
        if not msg:
            return
        self.chat_input.delete(0, "end")
        self._append_chat_message("user", msg)
        if self.on_send_chat:
            threading.Thread(target=lambda: self.on_send_chat(msg), daemon=True).start()

    # ==========================================
    # VIEW 3: QUICK TOOLS VIEW
    # ==========================================
    def _build_tools_view(self):
        tools_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["tools"] = tools_frame
        tools_frame.grid_columnconfigure(0, weight=1)
        tools_frame.grid_columnconfigure(1, weight=1)

        # Quick Actions Grid
        actions = [
            ("▶️ Play YouTube Music", "Searches and plays top song or video directly", lambda: self._quick_tool("play_video", "lofi hip hop")),
            ("🌐 Open LeetCode Daily", "Jumps straight to the daily LeetCode challenge", lambda: self._quick_tool("open_leetcode", "daily")),
            ("💻 Open VS Code", "Launches Visual Studio Code on project", lambda: self._quick_tool("open_app", "code")),
            ("📁 Open Downloads Folder", "Opens Downloads folder in Windows Explorer", lambda: self._quick_tool("open_folder", "Downloads")),
            ("🔇 Mute / Unmute System", "Toggles Windows master volume mute", lambda: self._quick_tool("system_control", "mute")),
            ("🔊 Volume Up", "Increases master audio volume", lambda: self._quick_tool("system_control", "volume_up")),
        ]

        for i, (title, desc, cmd) in enumerate(actions):
            r = i // 2
            c = i % 2
            card = ctk.CTkFrame(
                tools_frame,
                fg_color="#161720",
                border_width=1,
                border_color="#232532",
                corner_radius=10,
                height=90
            )
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

            t_lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color="#f8fafc")
            t_lbl.pack(anchor="w", padx=14, pady=(12, 2))

            d_lbl = ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=11), text_color="#64748b")
            d_lbl.pack(anchor="w", padx=14, pady=(0, 8))

            btn = ctk.CTkButton(
                card,
                text="Execute",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                width=80,
                height=26,
                corner_radius=6,
                command=cmd
            )
            btn.pack(anchor="e", padx=14, pady=(0, 10))

    def _quick_tool(self, tool_name: str, arg_val: str):
        if self.on_send_chat:
            cmd = f"Execute action: {tool_name} with '{arg_val}'"
            threading.Thread(target=lambda: self.on_send_chat(cmd), daemon=True).start()

    # ==========================================
    # VIEW 4: SETTINGS VIEW
    # ==========================================
    def _build_settings_view(self):
        settings_frame = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="#101117",
            border_width=1,
            border_color="#1c1d27",
            corner_radius=10
        )
        self.views["settings"] = settings_frame
        settings_frame.grid_columnconfigure(0, weight=1)

        # Section 1: Voice Session & Follow-Up Listening
        s1 = self._create_settings_section(settings_frame, "Voice Conversation & Listening Window")

        # Row 1: Follow-up timeout
        row1 = ctk.CTkFrame(s1, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(8, 2))
        ctk.CTkLabel(row1, text="Follow-Up Listening Window:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")
        
        curr_timeout_str = f"{int(self.config.get('follow_up_timeout', 10))}s"
        self.timeout_seg = ctk.CTkSegmentedButton(
            row1,
            values=["5s", "10s", "15s", "20s", "30s"],
            command=self._on_timeout_change,
            selected_color="#2563eb",
            height=28
        )
        self.timeout_seg.set(curr_timeout_str)
        self.timeout_seg.pack(side="right")

        ctk.CTkLabel(
            s1,
            text="Keeps mic open for follow-up questions without needing the hotkey again.",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Row 2: Silence limit (Endpointing)
        row2 = ctk.CTkFrame(s1, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(6, 2))
        ctk.CTkLabel(row2, text="Silence Cutoff Speed:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")

        curr_silence = self.config.get("silence_limit", 0.55)
        curr_silence_str = f"{curr_silence:.2f}s" if curr_silence in (0.4, 0.55, 0.8, 1.2) else "0.55s"
        self.silence_seg = ctk.CTkSegmentedButton(
            row2,
            values=["0.40s", "0.55s", "0.80s", "1.20s"],
            command=self._on_silence_change,
            selected_color="#2563eb",
            height=28
        )
        self.silence_seg.set(curr_silence_str)
        self.silence_seg.pack(side="right")

        ctk.CTkLabel(
            s1,
            text="How quickly Jarvis detects you finished speaking and begins transcription.",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Row 3: Sound Effects (Wake/Sleep Chimes)
        row3 = ctk.CTkFrame(s1, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(6, 2))
        ctk.CTkLabel(row3, text="Audio Chimes (Wake / Sleep SFX):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")
        self.sfx_switch = ctk.CTkSwitch(row3, text="Enabled", command=self._on_sfx_toggle)
        if self.config.get("sfx_enabled", True):
            self.sfx_switch.select()
        else:
            self.sfx_switch.deselect()
        self.sfx_switch.pack(side="right")

        ctk.CTkLabel(
            s1,
            text="Plays C5->E5 chime when waking, and D5->A4 sleep chime when entering standby.",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # Row 4: Voice Dismissal Commands
        row4 = ctk.CTkFrame(s1, fg_color="transparent")
        row4.pack(fill="x", padx=14, pady=(6, 2))
        ctk.CTkLabel(row4, text="Voice Sleep Commands:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")
        self.dismissal_switch = ctk.CTkSwitch(row4, text="Active", command=self._on_dismissal_toggle)
        if self.config.get("voice_dismissal_enabled", True):
            self.dismissal_switch.select()
        else:
            self.dismissal_switch.deselect()
        self.dismissal_switch.pack(side="right")

        ctk.CTkLabel(
            s1,
            text="Say 'that's all bye', 'terminate yourself', or 'close' to put Jarvis to sleep immediately.",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(anchor="w", padx=14, pady=(0, 12))

        # Section 2: Hotkeys & Wake Word
        s2 = self._create_settings_section(settings_frame, "Push-to-Talk & Wake Word")

        row_hk = ctk.CTkFrame(s2, fg_color="transparent")
        row_hk.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(row_hk, text="Push-to-Talk Shortcuts:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")
        ctk.CTkLabel(row_hk, text="Ctrl+Shift+Space  |  Ctrl+Alt+J  |  Ctrl+Win", font=ctk.CTkFont(size=12), text_color="#38bdf8").pack(side="right")

        row_ww = ctk.CTkFrame(s2, fg_color="transparent")
        row_ww.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(row_ww, text="Wake Word ('Hey Jarvis'):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")
        self.wake_switch = ctk.CTkSwitch(row_ww, text="Active", command=self._toggle_wake)
        if self.config.get("wake_word_enabled", True):
            self.wake_switch.select()
        else:
            self.wake_switch.deselect()
        self.wake_switch.pack(side="right")

        # Section 3: AI Models & API Key
        s3 = self._create_settings_section(settings_frame, "AI Model & OpenRouter API")

        row_m1 = ctk.CTkFrame(s3, fg_color="transparent")
        row_m1.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(row_m1, text="Primary LLM:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")
        ctk.CTkLabel(row_m1, text="DeepSeek 4.1 Flash (Auto-Fallback: openrouter/free)", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(side="right")

        row_m2 = ctk.CTkFrame(s3, fg_color="transparent")
        row_m2.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(row_m2, text="Speech STT Engine:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")
        ctk.CTkLabel(row_m2, text="NVIDIA Parakeet-EOU INT8 (Sub-50ms + Silence Trim)", font=ctk.CTkFont(size=12), text_color="#10b981").pack(side="right")

        row_key = ctk.CTkFrame(s3, fg_color="transparent")
        row_key.pack(fill="x", padx=14, pady=(8, 14))
        ctk.CTkLabel(row_key, text="OpenRouter Key:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(side="left")

        current_key = os.getenv("OPENROUTER_API_KEY", "")
        masked_key = (current_key[:8] + "..." + current_key[-6:]) if len(current_key) > 14 else current_key
        self.key_entry = ctk.CTkEntry(
            row_key,
            placeholder_text=masked_key or "Enter sk-or-v1-...",
            fg_color="#161720",
            border_color="#232532",
            width=260,
            height=32,
            corner_radius=6
        )
        self.key_entry.pack(side="right", padx=(8, 0))

        save_key_btn = ctk.CTkButton(
            row_key,
            text="Save",
            width=60,
            height=32,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            corner_radius=6,
            command=self._save_key
        )
        save_key_btn.pack(side="right")

    def _create_settings_section(self, parent, title: str) -> ctk.CTkFrame:
        container = ctk.CTkFrame(
            parent,
            fg_color="#161720",
            border_width=1,
            border_color="#232532",
            corner_radius=10
        )
        container.pack(fill="x", padx=8, pady=8)

        t_lbl = ctk.CTkLabel(
            container,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f8fafc"
        )
        t_lbl.pack(anchor="w", padx=14, pady=(10, 4))
        return container

    def _on_timeout_change(self, value: str):
        try:
            val = float(value.replace("s", ""))
            self.config["follow_up_timeout"] = val
            save_config(self.config)
            if self.on_update_settings:
                self.on_update_settings(self.config)
        except Exception:
            pass

    def _on_silence_change(self, value: str):
        try:
            val = float(value.replace("s", ""))
            self.config["silence_limit"] = val
            save_config(self.config)
            if self.on_update_settings:
                self.on_update_settings(self.config)
        except Exception:
            pass

    def _on_sfx_toggle(self):
        state = bool(self.sfx_switch.get())
        self.config["sfx_enabled"] = state
        save_config(self.config)
        if self.on_update_settings:
            self.on_update_settings(self.config)

    def _on_dismissal_toggle(self):
        state = bool(self.dismissal_switch.get())
        self.config["voice_dismissal_enabled"] = state
        save_config(self.config)
        if self.on_update_settings:
            self.on_update_settings(self.config)

    def _toggle_wake(self):
        state = bool(self.wake_switch.get())
        self.config["wake_word_enabled"] = state
        save_config(self.config)
        if self.on_toggle_wake_word:
            self.on_toggle_wake_word(state)
        if self.on_update_settings:
            self.on_update_settings(self.config)

    def _save_key(self):
        val = self.key_entry.get().strip()
        if val and self.on_save_api_key:
            self.on_save_api_key(val)
            self.key_entry.delete(0, "end")
            self.key_entry.configure(placeholder_text="Saved!")

    def _handle_voice_click(self):
        if self.on_trigger_voice:
            threading.Thread(target=self.on_trigger_voice, daemon=True).start()

    def _handle_stop_click(self):
        try:
            self.root.withdraw()
        except Exception:
            pass
        if self.on_stop_jarvis:
            self.on_stop_jarvis()
        else:
            try:
                self.root.destroy()
            except Exception:
                pass
            os._exit(0)

    # ==========================================
    # WINDOW CONTROLS (SHOW / HIDE)
    # ==========================================
    def show(self):
        """Brings the dashboard smoothly to the foreground."""
        def _do_show():
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(150, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        self.root.after(0, _do_show)

    def hide(self):
        """Hides the dashboard to Windows system tray without terminating."""
        self.root.withdraw()


if __name__ == "__main__":
    app = JarvisDashboard()
    app.show()
    app.root.mainloop()
