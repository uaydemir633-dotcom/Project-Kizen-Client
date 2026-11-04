import json
import os
import queue
import re
import sqlite3
import threading
import time
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from google import genai
from openai import OpenAI

# ------------------- GEMINI THEME -------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PALETTE = {
    "bg_app":       "#131314",  # Gemini background
    "bg_sidebar":   "#1E1F20",  # Sidebar (Expanded)
    "bg_sidebar_2": "#282A2C",  # Hover / Selected
    "bg_input":     "#1E1F20",  # Input Bar Color
    "bg_hover":     "#333537",
    "text_hi":      "#E3E3E3",
    "text_mid":     "#C4C7C5",
    "text_lo":      "#8E918F",
    "accent":       "#A8C7FA",  # Gemini blue
    "accent_dark":  "#8AB4F8",
    "danger":       "#F28B82",
    "border":       "#444746",
}

# ------------------- CONSTANTS -------------------
CONFIG_PATH = os.path.expanduser("~/.kizen_config.json")
HISTORY_LIMIT = 40
FLUSH_INTERVAL = 0.05

GEMINI_MODEL_MAP = {"Gemini 2.5 Flash": "gemini-2.5-flash", "Gemini 2.5 Pro": "gemini-2.5-pro"}
OPENAI_MODEL_MAP = {"GPT-4o-mini": "gpt-4o-mini", "GPT-4o": "gpt-4o"}
OPENROUTER_MODEL_MAP = {"OpenRouter Auto": "openrouter/auto", "OR Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet"}
GROQ_MODEL_MAP = {"Groq Llama 3.3 70B": "llama-3.3-70b-versatile", "Groq Gemma 2 9B": "gemma2-9b-it"}

ALL_MODELS = list(GEMINI_MODEL_MAP) + list(OPENAI_MODEL_MAP) + list(OPENROUTER_MODEL_MAP) + list(GROQ_MODEL_MAP)


# ============================================================
# WIDGETS & HELPER
# ============================================================

class ToolTip:
    """Small tooltip that appears on hover."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, _event=None):
        if self.tip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2 - 15
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#E3E3E3", foreground="#000000", relief=tk.SOLID, borderwidth=0, font=("Segoe UI", 10))
        label.pack(ipadx=8, ipady=4)

    def hide_tip(self, _event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class MessageBubble(ctk.CTkFrame):
    def __init__(self, master, sender, text, model=None, is_user=False):
        super().__init__(master, fg_color="transparent")
        self.sender = sender
        self.model = model
        self.is_user = is_user
        self._raw_text = text
        self._labels = []
        self._finalized = False

        if is_user: self._build_user(text)
        else: self._build_ai(text)

    def _build_user(self, text):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="x", padx=20, pady=10)

        avatar = ctk.CTkLabel(outer, text="👤", width=32, height=32, corner_radius=16, fg_color=PALETTE["bg_hover"], font=ctk.CTkFont(size=14))
        avatar.pack(side="right", anchor="n", padx=(10, 0))

        bubble = ctk.CTkFrame(outer, fg_color=PALETTE["bg_sidebar_2"], corner_radius=18)
        bubble.pack(side="right", anchor="n", fill="x", expand=True)

        header = ctk.CTkFrame(bubble, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(header, text=self.sender, text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        self.body = ctk.CTkFrame(bubble, fg_color="transparent")
        self.body.pack(fill="x", padx=16, pady=(4, 12))
        
        lbl = ctk.CTkLabel(self.body, text=text, text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=14), wraplength=650, justify="left", anchor="w")
        lbl.pack(fill="x", anchor="w")
        self._labels.append(lbl)

    def _build_ai(self, text):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="x", padx=20, pady=10)

        avatar = ctk.CTkLabel(outer, text="⚡", width=32, height=32, corner_radius=16, fg_color=PALETTE["bg_hover"], text_color=PALETTE["accent"], font=ctk.CTkFont(size=16, weight="bold"))
        avatar.pack(side="left", anchor="n", padx=(0, 10))

        bubble = ctk.CTkFrame(outer, fg_color="transparent")
        bubble.pack(side="left", anchor="n", fill="x", expand=True)

        header = ctk.CTkFrame(bubble, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkLabel(header, text=self.model or "AI", text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        
        ctk.CTkButton(header, text="📋", width=24, height=24, corner_radius=6, fg_color="transparent", hover_color=PALETTE["bg_hover"], font=ctk.CTkFont(size=12), command=self._copy).pack(side="right", padx=(0, 10))
        
        self.body = ctk.CTkFrame(bubble, fg_color="transparent")
        self.body.pack(fill="x", padx=4, pady=(0, 4))
        
        if text: self._render_text(text)

    def _render_text(self, text):
        parts = re.split(r"(```[a-zA-Z0-9]*\n[\s\S]*?```)", text)
        for w in self.body.winfo_children(): w.destroy()
        self._labels.clear()

        for part in parts:
            if not part: continue
            if part.startswith("```"):
                nl = part.find("\n")
                code = part[nl + 1:] if nl >= 0 else part[3:]
                if code.endswith("```"): code = code[:-3]
                lbl = ctk.CTkLabel(self.body, text=code, text_color=PALETTE["text_hi"], fg_color="#0D0D12", font=ctk.CTkFont(family="Consolas", size=13), corner_radius=8, wraplength=650, justify="left", anchor="w", padx=12, pady=12)
            else:
                lbl = ctk.CTkLabel(self.body, text=part, text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=14), wraplength=650, justify="left", anchor="w")
            
            lbl.pack(fill="x", anchor="w", pady=(0, 4))
            self._labels.append(lbl)

    def append_text(self, text):
        self._raw_text += text
        if self._finalized: self._render_text(self._raw_text)
        else:
            if not self._labels:
                lbl = ctk.CTkLabel(self.body, text=text, text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=14), wraplength=650, justify="left", anchor="w")
                lbl.pack(fill="x", anchor="w")
                self._labels.append(lbl)
            else:
                current_text = self._labels[-1].cget("text")
                self._labels[-1].configure(text=current_text + text)

    def finalize(self):
        if self._finalized: return
        self._finalized = True
        self._render_text(self._raw_text)

    def _copy(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self._raw_text)
            if self.winfo_toplevel():
                toast = getattr(self.winfo_toplevel(), "_toast", None)
                if toast: toast("✓ Copied")
        except Exception: pass


class Toast(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=PALETTE["bg_sidebar_2"], corner_radius=20)
        self.label = ctk.CTkLabel(self, text="", text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=13), padx=20, pady=10)
        self.label.pack()
        self._after_id = None

    def show(self, text, duration=1800):
        self.label.configure(text=text)
        self.place(relx=0.5, rely=0.04, anchor="n")
        self.lift()
        if self._after_id: self.after_cancel(self._after_id)
        self._after_id = self.after(duration, self.place_forget)


# ============================================================
# DIALOGS
# ============================================================
class _TextInputDialog(ctk.CTkToplevel):
    TITLE, GEOMETRY, HEADER, PLACEHOLDER, SAVE_LABEL = "", "350x200", "", "", "Save"
    def __init__(self, parent, current_value, callback):
        super().__init__(parent)
        self.title(self.TITLE); self.geometry(self.GEOMETRY); self.resizable(False, False)
        try: self.attributes("-topmost", True)
        except: pass
        self.configure(fg_color=PALETTE["bg_app"]); self.callback = callback
        
        ctk.CTkLabel(self, text=self.HEADER, font=ctk.CTkFont(size=16, weight="bold"), text_color=PALETTE["text_hi"]).pack(pady=(20, 15))
        self.entry = ctk.CTkEntry(self, placeholder_text=self.PLACEHOLDER, width=280, height=40, corner_radius=10, border_width=0, fg_color=PALETTE["bg_sidebar_2"])
        self.entry.insert(0, current_value); self.entry.pack(pady=10)
        self.entry.bind("<Return>", lambda _e: self._save())
        ctk.CTkButton(self, text=self.SAVE_LABEL, height=40, corner_radius=10, fg_color=PALETTE["accent"], text_color="#000000", hover_color=PALETTE["accent_dark"], command=self._save).pack(pady=20)
        self.entry.focus_set()

    def _save(self):
        val = self.entry.get().strip()
        if val: self.callback(val)
        self.destroy()

class ProfileDialog(_TextInputDialog):
    TITLE, HEADER, PLACEHOLDER = "Profile", "Profile Name", "Enter your name"

class EditChatDialog(_TextInputDialog):
    TITLE, HEADER, PLACEHOLDER = "Rename Chat", "New Title", "Enter title"


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("Settings"); self.geometry("520x640"); self.resizable(False, False)
        try: self.attributes("-topmost", True)
        except: pass
        self.configure(fg_color=PALETTE["bg_app"]); self.app = app

        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=24, weight="bold"), text_color=PALETTE["text_hi"]).pack(pady=(20, 10), anchor="w", padx=30)

        tabs = ctk.CTkTabview(self, fg_color=PALETTE["bg_app"], corner_radius=12, segmented_button_fg_color=PALETTE["bg_sidebar"], segmented_button_selected_color=PALETTE["bg_sidebar_2"], segmented_button_selected_hover_color=PALETTE["bg_sidebar_2"], text_color=PALETTE["text_hi"], width=460, height=480)
        tabs.pack(pady=10, padx=20, fill="both", expand=True)
        tabs.add("API Keys"); tabs.add("About")

        api_tab = tabs.tab("API Keys")
        self.openai_entry = self._add_key_field(api_tab, "OpenAI API Key", app.OPENAI_API_KEY)
        self.gemini_entry = self._add_key_field(api_tab, "Gemini API Key", app.GEMINI_API_KEY)
        self.openrouter_entry = self._add_key_field(api_tab, "OpenRouter API Key", app.OPENROUTER_API_KEY)
        self.groq_entry = self._add_key_field(api_tab, "Groq API Key", app.GROQ_API_KEY)

        about_tab = tabs.tab("About")
        ctk.CTkLabel(about_tab, text="Project-Kizen\n\nMulti-provider AI client.", font=ctk.CTkFont(size=14), text_color=PALETTE["text_mid"]).pack(pady=40)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15, fill="x", padx=20)
        ctk.CTkButton(btn_frame, text="Test", fg_color=PALETTE["bg_sidebar"], hover_color=PALETTE["bg_sidebar_2"], height=40, corner_radius=20, command=self._test_connection).pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="Save", fg_color=PALETTE["accent"], text_color="#000000", hover_color=PALETTE["accent_dark"], font=ctk.CTkFont(weight="bold"), height=40, corner_radius=20, command=self._save).pack(side="right", expand=True, fill="x", padx=(8, 0))

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(0, 10))

    @staticmethod
    def _add_key_field(parent, label, value):
        ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=13, weight="bold"), text_color=PALETTE["text_hi"], anchor="w").pack(anchor="w", padx=16, pady=(15, 4))
        entry = ctk.CTkEntry(parent, width=420, height=40, show="•", corner_radius=10, border_width=0, fg_color=PALETTE["bg_sidebar"])
        entry.insert(0, value)
        entry.pack(padx=16)
        return entry

    def _test_connection(self):
        self.status_label.configure(text="Testing...", text_color=PALETTE["text_mid"]); self.update_idletasks()
        errors = []
        for name, entry, base_url in [("OpenAI", self.openai_entry, None), ("Gemini", self.gemini_entry, "genai"), ("OpenRouter", self.openrouter_entry, "https://openrouter.ai/api/v1"), ("Groq", self.groq_entry, "https://api.groq.com/openai/v1")]:
            key = entry.get().strip()
            if key and not key.startswith("ENTER_"):
                try:
                    if base_url == "genai": genai.Client(api_key=key).models.list()
                    else: OpenAI(api_key=key, base_url=base_url).models.list() if base_url else OpenAI(api_key=key).models.list()
                except Exception as e: errors.append(f"{name} error")
        if not errors: self.status_label.configure(text="✓ Connections Successful", text_color="#81C995")
        else: self.status_label.configure(text="✗ " + ", ".join(errors), text_color=PALETTE["danger"])

    def _save(self):
        self.app.OPENAI_API_KEY = self.openai_entry.get().strip()
        self.app.GEMINI_API_KEY = self.gemini_entry.get().strip()
        self.app.OPENROUTER_API_KEY = self.openrouter_entry.get().strip()
        self.app.GROQ_API_KEY = self.groq_entry.get().strip()
        self.app.save_config(); self.destroy()


# ============================================================
# MAIN APPLICATION
# ============================================================

class ProjectKizenClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Project-Kizen")
        self.geometry("1280x800")
        self.minsize(1000, 700)
        self.configure(fg_color=PALETTE["bg_app"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_session_id = None
        self.sidebar_expanded = True
        self._is_responding = False
        self._db_lock = threading.Lock()
        self._ui_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._current_bubble = None

        cfg = self._load_config()
        self.OPENAI_API_KEY = cfg.get("openai_key", "ENTER_OPENAI_API_KEY_HERE")
        self.GEMINI_API_KEY = cfg.get("gemini_key", "ENTER_GEMINI_API_KEY_HERE")
        self.OPENROUTER_API_KEY = cfg.get("openrouter_key", "ENTER_OPENROUTER_API_KEY_HERE")
        self.GROQ_API_KEY = cfg.get("groq_key", "ENTER_GROQ_API_KEY_HERE")
        self.profile_name = cfg.get("profile", "Admin")
        initial_model = cfg.get("model", "Gemini 2.5 Flash")

        self._init_database()
        self._build_expanded_sidebar()
        self._build_collapsed_sidebar()
        self._build_main_area(initial_model)

        self._toast = Toast(self)
        self.load_sessions_list()
        self._create_new_chat_internal()

        self._poll_ui_queue()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"openai_key": self.OPENAI_API_KEY, "gemini_key": self.GEMINI_API_KEY, "openrouter_key": self.OPENROUTER_API_KEY, "groq_key": self.GROQ_API_KEY, "profile": self.profile_name, "model": self.model_selector.get()}, f, indent=2)
        except: pass

    # ---------------------------------------------------------
    # SIDEBAR (Expanded)
    # ---------------------------------------------------------
    def _build_expanded_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=PALETTE["bg_sidebar"])
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1)
        self.sidebar_frame.grid_propagate(False)

        # Top Area
        top_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        
        ctk.CTkLabel(top_frame, text="⚡ Project-Kizen", font=ctk.CTkFont(size=18, weight="bold"), text_color=PALETTE["text_hi"]).pack(side="left")
        
        collapse_btn = ctk.CTkButton(top_frame, text="◫", width=36, height=36, corner_radius=18, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], text_color=PALETTE["text_mid"], font=ctk.CTkFont(size=18), command=self.toggle_sidebar)
        collapse_btn.pack(side="right")
        ToolTip(collapse_btn, "Close sidebar")

        # Menu Area
        menu_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        menu_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self._add_menu_btn(menu_frame, "✏️", "New chat", self.create_new_chat)

        # History Area
        hist_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        hist_frame.grid(row=2, column=0, sticky="nsew", padx=10)
        
        ctk.CTkLabel(hist_frame, text="All", font=ctk.CTkFont(size=11, weight="bold"), text_color=PALETTE["text_lo"], anchor="w").pack(fill="x", padx=10, pady=(10, 4))
        
        self.history_scroll_frame = ctk.CTkScrollableFrame(hist_frame, fg_color="transparent")
        self.history_scroll_frame.pack(fill="both", expand=True)

        # Bottom Area
        bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=15)
        
        self.profile_btn = ctk.CTkButton(bottom_frame, text=f"👤  {self.profile_name}", height=40, corner_radius=20, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], anchor="w", font=ctk.CTkFont(size=13, weight="bold"), text_color=PALETTE["text_mid"], command=self.open_profile_dialog)
        self.profile_btn.pack(side="left", fill="x", expand=True)
        
        ctk.CTkButton(bottom_frame, text="⚙️", width=40, height=40, corner_radius=20, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], font=ctk.CTkFont(size=18), text_color=PALETTE["text_mid"], command=self.open_settings_dialog).pack(side="right")

    def _add_menu_btn(self, parent, icon, text, cmd):
        btn = ctk.CTkButton(parent, text=f"{icon}  {text}", height=40, corner_radius=20, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], anchor="w", font=ctk.CTkFont(size=13), text_color=PALETTE["text_hi"], command=cmd)
        btn.pack(fill="x", pady=1)

    # ---------------------------------------------------------
    # SIDEBAR (Collapsed)
    # ---------------------------------------------------------
    def _build_collapsed_sidebar(self):
        self.icon_frame = ctk.CTkFrame(self, width=70, corner_radius=0, fg_color=PALETTE["bg_sidebar"])
        
        # Top
        top_frame = ctk.CTkFrame(self.icon_frame, fg_color="transparent")
        top_frame.pack(fill="x", pady=15)
        
        expand_btn = ctk.CTkButton(top_frame, text="◫", width=44, height=44, corner_radius=22, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], text_color=PALETTE["text_mid"], font=ctk.CTkFont(size=18), command=self.toggle_sidebar)
        expand_btn.pack()
        ToolTip(expand_btn, "Open sidebar")

        # Icons
        def add_icon(icon, tooltip, cmd):
            btn = ctk.CTkButton(self.icon_frame, text=icon, width=44, height=44, corner_radius=22, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], font=ctk.CTkFont(size=18), text_color=PALETTE["text_hi"], command=cmd)
            btn.pack(pady=8)
            ToolTip(btn, tooltip)

        add_icon("✏️", "New chat", self.create_new_chat)

        # Bottom
        bottom_frame = ctk.CTkFrame(self.icon_frame, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=15)
        
        set_btn = ctk.CTkButton(bottom_frame, text="⚙️", width=44, height=44, corner_radius=22, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], font=ctk.CTkFont(size=18), text_color=PALETTE["text_mid"], command=self.open_settings_dialog)
        set_btn.pack()
        ToolTip(set_btn, "Settings")
        
        prof_btn = ctk.CTkButton(bottom_frame, text="👤", width=44, height=44, corner_radius=22, fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"], font=ctk.CTkFont(size=18), text_color=PALETTE["text_mid"], command=self.open_profile_dialog)
        prof_btn.pack(pady=(8,0))
        ToolTip(prof_btn, "Account")

    # ---------------------------------------------------------
    # MAIN AREA
    # ---------------------------------------------------------
    def _build_main_area(self, initial_model):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Top Bar
        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=60)
        self.top_bar.grid(row=0, column=0, sticky="ew")
        self.top_bar.grid_propagate(False)
        
        self._top_title = ctk.CTkLabel(self.top_bar, text="New Chat", font=ctk.CTkFont(size=18, weight="bold"), text_color=PALETTE["text_hi"])
        self._top_title.pack(side="left", padx=20, pady=20)

        # Center Area
        self.center_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.center_frame.grid(row=1, column=0, sticky="nsew")
        self.center_frame.grid_rowconfigure(0, weight=1)
        self.center_frame.grid_columnconfigure(0, weight=1)

        # --- WELCOME SCREEN ---
        self.welcome_frame = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        self.welcome_frame.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkFrame(self.welcome_frame, fg_color="transparent", height=180).pack()
        
        ctk.CTkLabel(self.welcome_frame, text="⚡", font=ctk.CTkFont(size=50), text_color=PALETTE["accent"]).pack()
        ctk.CTkLabel(self.welcome_frame, text="Where should we start?", font=ctk.CTkFont(family="Segoe UI", size=36), text_color=PALETTE["text_mid"]).pack(pady=(10, 40))
        
        # Center Input Bar
        self.welcome_input_frame = ctk.CTkFrame(self.welcome_frame, fg_color=PALETTE["bg_input"], corner_radius=30, height=60)
        self.welcome_input_frame.pack(fill="x", padx=180)
        self.welcome_input_frame.pack_propagate(False)
        
        ctk.CTkButton(self.welcome_input_frame, text="＋", width=40, height=40, corner_radius=20, fg_color="transparent", hover_color=PALETTE["bg_hover"], font=ctk.CTkFont(size=20), text_color=PALETTE["text_hi"]).pack(side="left", padx=10)
        
        self.welcome_entry = ctk.CTkEntry(self.welcome_input_frame, placeholder_text="Ask Project-Kizen", border_width=0, fg_color="transparent", font=ctk.CTkFont(size=15), text_color=PALETTE["text_hi"])
        self.welcome_entry.pack(side="left", fill="both", expand=True, padx=5)
        self.welcome_entry.bind("<Return>", lambda e: self._send_from_welcome())

        self.welcome_model_selector = ctk.CTkOptionMenu(self.welcome_input_frame, values=ALL_MODELS, width=160, height=36, corner_radius=18, fg_color=PALETTE["bg_input"], button_color=PALETTE["bg_input"], button_hover_color=PALETTE["bg_hover"], text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=12))
        self.welcome_model_selector.pack(side="right", padx=10)
        self.welcome_model_selector.set(initial_model if initial_model in ALL_MODELS else "Gemini 2.5 Flash")

        # --- CHAT SCREEN ---
        self.chat_scroll = ctk.CTkScrollableFrame(self.center_frame, fg_color="transparent")
        self.chat_scroll.grid(row=0, column=0, sticky="nsew")

        # --- BOTTOM INPUT BAR ---
        self.chat_input_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.chat_input_container.grid(row=2, column=0, sticky="ew", padx=180, pady=(0, 30))
        
        self.chat_input_frame = ctk.CTkFrame(self.chat_input_container, fg_color=PALETTE["bg_input"], corner_radius=30, height=60)
        self.chat_input_frame.pack(fill="x")
        self.chat_input_frame.pack_propagate(False)
        
        ctk.CTkButton(self.chat_input_frame, text="＋", width=40, height=40, corner_radius=20, fg_color="transparent", hover_color=PALETTE["bg_hover"], font=ctk.CTkFont(size=20), text_color=PALETTE["text_hi"]).pack(side="left", padx=10)
        
        self.prompt_entry = ctk.CTkEntry(self.chat_input_frame, placeholder_text="Ask Project-Kizen", border_width=0, fg_color="transparent", font=ctk.CTkFont(size=15), text_color=PALETTE["text_hi"])
        self.prompt_entry.pack(side="left", fill="both", expand=True, padx=5)
        self.prompt_entry.bind("<Return>", self._on_enter_key)
        
        self.send_btn = ctk.CTkButton(self.chat_input_frame, text="↑", width=40, height=40, corner_radius=20, fg_color=PALETTE["accent"], hover_color=PALETTE["accent_dark"], font=ctk.CTkFont(size=18, weight="bold"), text_color="#000000", command=self.send_message)
        self.send_btn.pack(side="right", padx=10)

        self.chat_model_selector = ctk.CTkOptionMenu(self.chat_input_frame, values=ALL_MODELS, width=160, height=36, corner_radius=18, fg_color=PALETTE["bg_input"], button_color=PALETTE["bg_input"], button_hover_color=PALETTE["bg_hover"], text_color=PALETTE["text_hi"], font=ctk.CTkFont(size=12), command=self._on_model_change)
        self.chat_model_selector.pack(side="right", padx=10)
        self.chat_model_selector.set(initial_model if initial_model in ALL_MODELS else "Gemini 2.5 Flash")

        self.model_selector = self.chat_model_selector # Reference for settings

    # ---------------------------------------------------------
    # FUNCTIONS
    # ---------------------------------------------------------
    def toggle_sidebar(self):
        if self.sidebar_expanded:
            self.sidebar_frame.grid_remove()
            self.icon_frame.grid(row=0, column=0, sticky="nsew")
            self.sidebar_expanded = False
        else:
            self.icon_frame.grid_remove()
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.sidebar_expanded = True

    def _on_model_change(self, _val=None):
        self.welcome_model_selector.set(self.chat_model_selector.get())
        self.save_config()

    def _send_from_welcome(self):
        text = self.welcome_entry.get().strip()
        if text:
            self.prompt_entry.delete(0, "end")
            self.prompt_entry.insert(0, text)
            self.send_message()

    def create_new_chat(self):
        if self._is_responding: return
        self._create_new_chat_internal()

    def _create_new_chat_internal(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = "New Chat"
        with self._db_lock:
            self.cursor.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", (title, timestamp))
            self.conn.commit()
            self.current_session_id = self.cursor.lastrowid
        self.clear_chat_display()
        self._set_welcome_visible(True)
        self._top_title.configure(text=title)
        self.load_sessions_list()

    def _set_welcome_visible(self, visible):
        if visible:
            self.top_bar.grid_remove()
            self.chat_scroll.grid_remove()
            self.chat_input_container.grid_remove()
            self.welcome_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.welcome_frame.grid_remove()
            self.top_bar.grid(row=0, column=0, sticky="ew")
            self.chat_scroll.grid(row=1, column=0, sticky="nsew")
            self.chat_input_container.grid(row=2, column=0, sticky="ew", padx=180, pady=(0, 30))

    def load_sessions_list(self, filter_text=""):
        for widget in self.history_scroll_frame.winfo_children(): widget.destroy()
        with self._db_lock:
            if filter_text: self.cursor.execute("SELECT id, title, created_at FROM sessions WHERE LOWER(title) LIKE ? ORDER BY id DESC", (f"%{filter_text.lower()}%",))
            else: self.cursor.execute("SELECT id, title, created_at FROM sessions ORDER BY id DESC")
            sessions = self.cursor.fetchall()
        for sid, title, c_at in sessions: self._build_session_row(sid, title)

    def _build_session_row(self, session_id, title):
        is_active = (session_id == self.current_session_id)
        row = ctk.CTkFrame(self.history_scroll_frame, fg_color=PALETTE["bg_sidebar_2"] if is_active else "transparent", corner_radius=20)
        row.pack(fill="x", pady=2, padx=5)
        
        btn = ctk.CTkButton(row, text=title, fg_color="transparent", hover_color=PALETTE["bg_hover"], anchor="w", font=ctk.CTkFont(size=13), text_color=PALETTE["text_hi"], height=40, corner_radius=18, command=lambda sid=session_id: self.load_session(sid))
        btn.pack(side="left", fill="x", expand=True, padx=4, pady=2)
        
        dots = ctk.CTkButton(row, text="...", width=28, height=28, corner_radius=6, fg_color="transparent", hover_color=PALETTE["bg_hover"], font=ctk.CTkFont(size=14), text_color=PALETTE["text_mid"], command=lambda sid=session_id, t=title, b=row: self._show_chat_menu(sid, t, b))
        dots.pack(side="right", padx=(0, 4))
        if not is_active:
            dots.configure(text_color=PALETTE["bg_sidebar_2"])
            row.bind("<Enter>", lambda _e: dots.configure(text_color=PALETTE["text_mid"]))
            row.bind("<Leave>", lambda _e: dots.configure(text_color=PALETTE["bg_sidebar_2"]))

    def _show_chat_menu(self, session_id, title, widget):
        menu = tk.Menu(self, tearoff=0, bg=PALETTE["bg_sidebar_2"], fg=PALETTE["text_hi"], activebackground=PALETTE["bg_hover"], activeforeground=PALETTE["text_hi"], bd=0, relief="flat")
        menu.add_command(label="✏️  Rename", command=lambda: EditChatDialog(self, title, lambda n: self.rename_session(session_id, n)))
        menu.add_command(label="🗑️  Delete", foreground=PALETTE["danger"], command=lambda: self.delete_session(session_id))
        try:
            x = widget.winfo_rootx() + widget.winfo_width() - 110
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            menu.tk_popup(x, y)
        finally: menu.grab_release()

    def load_session(self, session_id):
        if self._is_responding: return
        self.current_session_id = session_id
        with self._db_lock:
            self.cursor.execute("SELECT sender, message, model FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
            messages = self.cursor.fetchall()
            self.cursor.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
            row = self.cursor.fetchone()

        self.clear_chat_display()
        for sender, msg, model in messages:
            self._add_bubble(sender=sender, text=msg, model=model, is_user=(sender != "AI"))

        if not messages: self._set_welcome_visible(True)
        else: self._set_welcome_visible(False)

        if row: self._top_title.configure(text=row[0])
        self.load_sessions_list()
        self._scroll_to_bottom()

    def rename_session(self, session_id, new_title):
        with self._db_lock:
            self.cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
            self.conn.commit()
        if session_id == self.current_session_id: self._top_title.configure(text=new_title)
        self.load_sessions_list()

    def delete_session(self, session_id):
        if self._is_responding: return
        if not messagebox.askyesno("Delete", "Are you sure you want to delete this chat?", parent=self): return
        with self._db_lock:
            self.cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self.conn.commit()
        if self.current_session_id == session_id: self._create_new_chat_internal()
        else: self.load_sessions_list()

    def clear_chat_display(self):
        for w in self.chat_scroll.winfo_children(): w.destroy()
        self._current_bubble = None

    def _add_bubble(self, sender, text, model=None, is_user=False):
        bubble = MessageBubble(self.chat_scroll, sender=sender, text=text, model=model, is_user=is_user)
        bubble.pack(fill="x", pady=4)
        self._scroll_to_bottom()
        return bubble

    def send_message(self):
        if self._is_responding: return
        prompt = self.prompt_entry.get().strip()
        if not prompt: return

        model = self.chat_model_selector.get()
        self.prompt_entry.delete(0, "end")
        self.welcome_entry.delete(0, "end")

        self._set_welcome_visible(False)
        self._add_bubble(sender=self.profile_name, text=prompt, is_user=True)
        self.save_message_to_db(self.profile_name, prompt)

        ai_bubble = self._add_bubble(sender=model, text="▌ Thinking...", model=model, is_user=False)
        self._current_bubble = ai_bubble

        session_id = self.current_session_id
        self._stop_event.clear()
        self._is_responding = True

        self.send_btn.configure(text="■", fg_color=PALETTE["danger"], hover_color="#C03030", command=self.stop_response)
        threading.Thread(target=self._fetch_response, args=(model, session_id), daemon=True).start()

    def stop_response(self):
        if self._is_responding: self._stop_event.set()

    def _append_chunk(self, text):
        if self._current_bubble:
            if self._current_bubble._raw_text == "▌ Thinking...":
                self._current_bubble._raw_text = ""
                for w in self._current_bubble.body.winfo_children(): w.destroy()
                self._current_bubble._labels.clear()
            self._current_bubble.append_text(text)
            self._scroll_to_bottom()

    def _fetch_response(self, model, session_id):
        response_text = ""
        buffer = ""
        last_flush = time.monotonic()
        stopped = False
        try:
            for chunk in self._stream_response(model, session_id):
                if self._stop_event.is_set(): stopped = True; break
                response_text += chunk
                buffer += chunk
                now = time.monotonic()
                if now - last_flush >= FLUSH_INTERVAL:
                    self._post_ui(self._append_chunk, buffer); buffer = ""; last_flush = now
            if buffer: self._post_ui(self._append_chunk, buffer)
        except Exception as e:
            err = f"\n\n⚠️ Error: {e}"
            response_text += err
            self._post_ui(self._append_chunk, err)
            traceback.print_exc()
        finally:
            if stopped: response_text += " [stopped]"; self._post_ui(self._append_chunk, " [stopped]")
            if response_text: self.save_message_to_db("AI", response_text, model, session_id)
            self._post_ui(self._on_response_finished)

    def _on_response_finished(self):
        if self._current_bubble: 
            if self._current_bubble._raw_text == "▌ Thinking...": self._current_bubble._raw_text = "No response received."
            self._current_bubble.finalize()
        self._current_bubble = None
        self._is_responding = False
        self.send_btn.configure(text="↑", fg_color=PALETTE["accent"], hover_color=PALETTE["accent_dark"], text_color="#000000", command=self.send_message)
        self.prompt_entry.focus_set()
        self._scroll_to_bottom()

    def _stream_response(self, model, session_id):
        history = self._get_chat_history(session_id)
        if not history: raise RuntimeError("History is empty.")

        if model in GEMINI_MODEL_MAP:
            if not self.GEMINI_API_KEY or self.GEMINI_API_KEY.startswith("ENTER_"): raise RuntimeError("Missing Gemini API key.")
            contents = [{"role": "user" if m["role"]=="user" else "model", "parts":[{"text": m["content"]}]} for m in history]
            client = genai.Client(api_key=self.GEMINI_API_KEY)
            for chunk in client.models.generate_content_stream(model=GEMINI_MODEL_MAP[model], contents=contents):
                if getattr(chunk, "text", None): yield chunk.text
        elif model in OPENAI_MODEL_MAP:
            if not self.OPENAI_API_KEY or self.OPENAI_API_KEY.startswith("ENTER_"): raise RuntimeError("Missing OpenAI API key.")
            client = OpenAI(api_key=self.OPENAI_API_KEY)
            for chunk in client.chat.completions.create(model=OPENAI_MODEL_MAP[model], messages=history, stream=True):
                if self._stop_event.is_set(): break
                if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
        elif model in OPENROUTER_MODEL_MAP:
            if not self.OPENROUTER_API_KEY or self.OPENROUTER_API_KEY.startswith("ENTER_"): raise RuntimeError("Missing OpenRouter API key.")
            client = OpenAI(api_key=self.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
            for chunk in client.chat.completions.create(model=OPENROUTER_MODEL_MAP[model], messages=history, stream=True):
                if self._stop_event.is_set(): break
                if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
        elif model in GROQ_MODEL_MAP:
            if not self.GROQ_API_KEY or self.GROQ_API_KEY.startswith("ENTER_"): raise RuntimeError("Missing Groq API key.")
            client = OpenAI(api_key=self.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
            for chunk in client.chat.completions.create(model=GROQ_MODEL_MAP[model], messages=history, stream=True):
                if self._stop_event.is_set(): break
                if chunk.choices[0].delta.content: yield chunk.choices[0].delta.content
        else: raise ValueError(f"Unknown model: {model}")

    def save_message_to_db(self, sender, message, model=None, session_id=None):
        sid = session_id or self.current_session_id
        if not sid: return
        with self._db_lock:
            self.cursor.execute("INSERT INTO messages (session_id, sender, message, model) VALUES (?, ?, ?, ?)", (sid, sender, message, model))
            self.conn.commit()

    def _get_chat_history(self, session_id):
        with self._db_lock:
            self.cursor.execute("SELECT sender, message FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, HISTORY_LIMIT))
            rows = self.cursor.fetchall()[::-1]
        return [{"role": "assistant" if s == "AI" else "user", "content": m} for s, m in rows]

    def open_profile_dialog(self): ProfileDialog(self, self.profile_name, self.update_profile_name)
    def open_settings_dialog(self): SettingsDialog(self, self)

    def update_profile_name(self, new_name):
        self.profile_name = new_name
        self.profile_btn.configure(text=f"👤  {self.profile_name}")
        self.save_config()

    def _on_close(self):
        self._stop_event.set()
        self.save_config()
        try: self.conn.close()
        finally: self.destroy()

    def _init_database(self):
        self.conn = sqlite3.connect("kizen_chats.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        with self._db_lock:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, sender TEXT, message TEXT, model TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id))")
            self.conn.commit()

    def _post_ui(self, callback, *args):
        self._ui_queue.put((callback, args))

    def _poll_ui_queue(self):
        try:
            while True:
                callback, args = self._ui_queue.get_nowait()
                try: callback(*args)
                except Exception: traceback.print_exc()
        except queue.Empty: pass
        if self.winfo_exists(): self.after(30, self._poll_ui_queue)

    def _scroll_to_bottom(self):
        try:
            self.chat_scroll.update_idletasks()
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception: pass

    def _on_enter_key(self, event):
        self.send_message()
        return "break"

    def _bind_shortcuts(self):
        self.bind("<Control-n>", lambda e: self.create_new_chat())
        self.bind("<Escape>", lambda e: self.stop_response() if self._is_responding else None)

if __name__ == "__main__":
    app = ProjectKizenClient()
    app.mainloop()
