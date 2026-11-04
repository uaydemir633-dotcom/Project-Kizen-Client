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

# ------------------- THEME -------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PALETTE = {
    "bg_app":       ("#FFFFFF", "#131314"),
    "bg_sidebar":   ("#F0F4F9", "#1E1F20"),
    "bg_sidebar_2": ("#DDE3EA", "#282A2C"),
    "bg_input":     ("#F0F4F9", "#1E1F20"),
    "bg_hover":     ("#E1E5EA", "#333537"),
    "bg_code":      ("#F3F4F6", "#0D0D12"),
    "text_hi":      ("#1F1F1F", "#E3E3E3"),
    "text_mid":     ("#444746", "#C4C7C5"),
    "text_lo":      ("#5F6368", "#8E918F"),
    "accent":       "#A8C7FA",
    "accent_dark":  "#8AB4F8",
    "danger":       ("#B3261E", "#F28B82"),
    "success":      ("#188038", "#81C995"),
    "border":       ("#C4C7C5", "#444746"),
}

# OPT: Font cache. ctk.CTkFont creates a Tcl font object on every call;
# caching avoids creating identical fonts for every widget/row rebuild.
_FONT_CACHE = {}
def _font(*args, **kwargs):
    try:
        key = (args, tuple(sorted(kwargs.items())))
        cached = _FONT_CACHE.get(key)
        if cached is not None:
            return cached
    except TypeError:
        return ctk.CTkFont(*args, **kwargs)  # unhashable -> don't cache
    font = ctk.CTkFont(*args, **kwargs)
    _FONT_CACHE[key] = font
    return font


def _tk_color(color):
    if isinstance(color, (tuple, list)):
        return color[0] if ctk.get_appearance_mode() == "Light" else color[1]
    return color


_scale_warned = False
def _window_scale(win):
    global _scale_warned
    try: return float(win._get_window_scaling())
    except Exception:
        if not _scale_warned:
            _scale_warned = True
            traceback.print_exc()
        return 1.0


def _fit_size(win, w, h, margin_w=40, margin_h=90):
    scale = _window_scale(win)
    max_w = int((win.winfo_screenwidth() - margin_w) / scale)
    max_h = int((win.winfo_screenheight() - margin_h) / scale)
    return max(200, min(w, max_w)), max(150, min(h, max_h))


def _center_on(win, parent, w, h):
    try:
        parent.update_idletasks()
        scale = _window_scale(win)
        w, h = _fit_size(win, w, h)
        pw, ph = int(w * scale), int(h * scale)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - pw) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - ph) // 2
        x = max(0, min(x, sw - pw))
        y = max(0, min(y, sh - ph - 50))
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        win.geometry(f"{w}x{h}")
    return w, h


def _make_modal(win, parent):
    try: win.transient(parent)
    except Exception: pass
    def _focus(tries=10):
        try:
            if not win.winfo_exists(): return
            win.lift(); win.focus_force(); win.grab_set()
        except tk.TclError:
            if tries > 0: win.after(100, lambda: _focus(tries - 1))
        except Exception:
            pass
    win.after(150, _focus)

    def _restore_parent_grab(event):
        if event.widget is not win: return
        try:
            if isinstance(parent, tk.Toplevel) and parent.winfo_exists():
                def _restore():
                    try:
                        if parent.winfo_exists():
                            parent.grab_set(); parent.focus_force()
                    except tk.TclError:
                        pass
                parent.after(50, _restore)
        except Exception:
            pass
    win.bind("<Destroy>", _restore_parent_grab, add="+")


# ------------------- CONSTANTS -------------------
CONFIG_PATH = os.path.expanduser("~/.kizen_config.json")
HISTORY_LIMIT = 40
FLUSH_INTERVAL = 0.05

GEMINI_MODEL_MAP     = {"Gemini 2.5 Flash": "gemini-2.5-flash", "Gemini 2.5 Pro": "gemini-2.5-pro"}
OPENAI_MODEL_MAP     = {"GPT-4o-mini": "gpt-4o-mini", "GPT-4o": "gpt-4o"}
OPENROUTER_MODEL_MAP = {"OpenRouter Auto": "openrouter/auto", "OR Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet"}
GROQ_MODEL_MAP       = {"Groq Llama 3.3 70B": "llama-3.3-70b-versatile", "Groq Llama 3.1 8B": "llama-3.1-8b-instant"}

BASE_MODELS = (
    list(GEMINI_MODEL_MAP) + list(OPENAI_MODEL_MAP) +
    list(OPENROUTER_MODEL_MAP) + list(GROQ_MODEL_MAP)
)

DB_PATH = "kizen_chats.db"
CHAT_STYLE = {"size": 14}

SYSTEM_PROMPT_PRESETS = {
    "— Select a preset —": None,
    "None (empty)": "",
    "Helpful Assistant": "You are a helpful, accurate and friendly assistant. Answer clearly and concisely.",
    "Senior Developer": ("You are a senior software engineer. Give production-quality code, explain trade-offs "
                         "briefly, point out bugs and edge cases, and prefer clear, idiomatic solutions."),
    "Türkçe Asistan": "Her zaman Türkçe yanıt ver. Açık, kısa ve doğru cevaplar ver.",
    "Translator (TR ⇄ EN)": ("You are a professional translator. If the input is Turkish, translate it to English; "
                             "otherwise translate it to Turkish. Output only the translation."),
    "Concise": "Answer as briefly as possible. No filler, no repetition.",
}

DEFAULT_SETTINGS = {
    "profile": "Admin",
    "default_model": "Gemini 2.5 Flash",
    "enter_sends": True,
    "auto_scroll": True,
    "confirm_on_close": True,
    "temperature": 0.7,
    "max_tokens": 0,
    "top_p": 1.0,
    "system_prompt": "",
    "history_limit": 40,
    "appearance_mode": "dark",
    "accent_color": "#A8C7FA",
    "chat_font_size": 14,
}

ACCENT_PRESETS = ["#A8C7FA", "#81C995", "#D0BCFF", "#F6AEA9", "#FDD663", "#78D9EC"]

LICENSE_TEXT = """MIT License

Copyright (c) 2026 Kizen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


def _darken(hex_color, factor=0.85):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return "#" + hex_color
    try:
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#" + hex_color
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


# ============================================================
# WIDGETS & HELPER
# ============================================================
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)
        widget.bind("<Button-1>", self.hide_tip)

    def show_tip(self, _event=None):
        if self.tip_window or not self.text: return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2 - 15
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tk.Label(tw, text=self.text, justify=tk.LEFT, background="#E3E3E3",
                 foreground="#000000", relief=tk.SOLID, borderwidth=0,
                 font=("Segoe UI", 10)).pack(ipadx=8, ipady=4)

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
        self._last_label_text = ""     # OPT: track last label's text to avoid cget() during streaming
        self._finalized = False
        if is_user: self._build_user(text)
        else: self._build_ai(text)

    def _build_user(self, text):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="x", padx=20, pady=10)
        avatar = ctk.CTkLabel(outer, text="👤", width=32, height=32, corner_radius=16,
                              fg_color=PALETTE["bg_hover"], font=_font(size=14))
        avatar.pack(side="right", anchor="n", padx=(10, 0))
        bubble = ctk.CTkFrame(outer, fg_color=PALETTE["bg_sidebar_2"], corner_radius=18)
        bubble.pack(side="right", anchor="n", fill="x", expand=True)
        header = ctk.CTkFrame(bubble, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(header, text=self.sender, text_color=PALETTE["text_hi"],
                     font=_font(size=13, weight="bold")).pack(side="left")
        self.body = ctk.CTkFrame(bubble, fg_color="transparent")
        self.body.pack(fill="x", padx=16, pady=(4, 12))
        lbl = ctk.CTkLabel(self.body, text=text, text_color=PALETTE["text_hi"],
                           font=_font(size=CHAT_STYLE["size"]), wraplength=650, justify="left", anchor="w")
        lbl.pack(fill="x", anchor="w")
        self._labels.append(lbl)
        self._last_label_text = text

    def _build_ai(self, text):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="x", padx=20, pady=10)
        avatar = ctk.CTkLabel(outer, text="⚡", width=32, height=32, corner_radius=16,
                              fg_color=PALETTE["bg_hover"], text_color=PALETTE["accent"],
                              font=_font(size=16, weight="bold"))
        avatar.pack(side="left", anchor="n", padx=(0, 10))
        bubble = ctk.CTkFrame(outer, fg_color="transparent")
        bubble.pack(side="left", anchor="n", fill="x", expand=True)
        header = ctk.CTkFrame(bubble, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkLabel(header, text=self.model or "AI", text_color=PALETTE["text_hi"],
                     font=_font(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="📋", width=24, height=24, corner_radius=6,
                      fg_color="transparent", hover_color=PALETTE["bg_hover"],
                      font=_font(size=12), command=self._copy, text_color=PALETTE["text_hi"]).pack(side="right", padx=(0, 10))
        self.body = ctk.CTkFrame(bubble, fg_color="transparent")
        self.body.pack(fill="x", padx=4, pady=(0, 4))
        if text: self._render_text(text)

    def _render_text(self, text):
        parts = re.split(r"(```[^\n`]*\n[\s\S]*?```)", text)
        for w in self.body.winfo_children(): w.destroy()
        self._labels.clear()
        self._last_label_text = ""
        for part in parts:
            if not part: continue
            if part.startswith("```"):
                nl = part.find("\n")
                code = part[nl + 1:] if nl >= 0 else part[3:]
                if code.endswith("```"): code = code[:-3]
                code = code.rstrip("\n")
                lbl = ctk.CTkLabel(self.body, text=code, text_color=PALETTE["text_hi"],
                                   fg_color=PALETTE["bg_code"],
                                   font=_font(family="Consolas", size=max(9, CHAT_STYLE["size"] - 1)),
                                   corner_radius=8, wraplength=650, justify="left", anchor="w",
                                   padx=12, pady=12)
                shown = code
            else:
                lbl = ctk.CTkLabel(self.body, text=part, text_color=PALETTE["text_hi"],
                                   font=_font(size=CHAT_STYLE["size"]), wraplength=650, justify="left", anchor="w")
                shown = part
            lbl.pack(fill="x", anchor="w", pady=(0, 4))
            self._labels.append(lbl)
            self._last_label_text = shown

    def append_text(self, text):
        # OPT: track text in a plain string instead of cget()+configure() per chunk
        self._raw_text += text
        if self._finalized:
            self._render_text(self._raw_text)
            return
        if not self._labels:
            lbl = ctk.CTkLabel(self.body, text=text, text_color=PALETTE["text_hi"],
                               font=_font(size=CHAT_STYLE["size"]), wraplength=650, justify="left", anchor="w")
            lbl.pack(fill="x", anchor="w")
            self._labels.append(lbl)
            self._last_label_text = text
        else:
            self._last_label_text += text
            self._labels[-1].configure(text=self._last_label_text)

    def reset(self):
        """OPT: clear streaming placeholder in one place."""
        self._raw_text = ""
        for w in self.body.winfo_children(): w.destroy()
        self._labels.clear()
        self._last_label_text = ""

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
                if toast: toast.show("✓ Copied")
        except Exception: pass


class Toast(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=PALETTE["bg_sidebar_2"], corner_radius=20)
        self.label = ctk.CTkLabel(self, text="", text_color=PALETTE["text_hi"],
                                  font=_font(size=13), padx=20, pady=10)
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
        self.title(self.TITLE); self.resizable(False, False)
        w, h = (int(v) for v in self.GEOMETRY.split("x"))
        _center_on(self, parent, w, h); _make_modal(self, parent)
        self.configure(fg_color=PALETTE["bg_app"]); self.callback = callback
        ctk.CTkLabel(self, text=self.HEADER, font=_font(size=16, weight="bold"),
                     text_color=PALETTE["text_hi"]).pack(pady=(20, 15))
        self.entry = ctk.CTkEntry(self, placeholder_text=self.PLACEHOLDER, width=280, height=40,
                                  corner_radius=10, border_width=0, fg_color=PALETTE["bg_sidebar_2"])
        self.entry.insert(0, current_value); self.entry.pack(pady=10)
        self.entry.bind("<Return>", lambda _e: self._save())
        ctk.CTkButton(self, text=self.SAVE_LABEL, height=40, corner_radius=10,
                      fg_color=PALETTE["accent"], text_color="#000000",
                      hover_color=PALETTE["accent_dark"], command=self._save).pack(pady=20)
        self.entry.focus_set()

    def _save(self):
        val = self.entry.get().strip()
        if val: self.callback(val)
        self.destroy()

class ProfileDialog(_TextInputDialog):
    TITLE, HEADER, PLACEHOLDER = "Profile", "Profile Name", "Enter your name"

class EditChatDialog(_TextInputDialog):
    TITLE, HEADER, PLACEHOLDER = "Rename Chat", "New Title", "Enter title"


class CustomModelDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback, existing=None):
        super().__init__(parent)
        self.title("Edit Custom Model" if existing else "Add Custom Model")
        self.resizable(True, True)
        _center_on(self, parent, 460, 520); _make_modal(self, parent)
        self.minsize(*_fit_size(self, 400, 360))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._save())
        self.configure(fg_color=PALETTE["bg_app"])
        self.callback = callback
        self.existing = existing or {}

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=16, side="bottom")
        ctk.CTkButton(btn_row, text="Cancel", fg_color=PALETTE["bg_sidebar"],
                      hover_color=PALETTE["bg_sidebar_2"], height=40, corner_radius=20,
                      command=self.destroy, text_color=PALETTE["text_hi"]).pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Save", fg_color=PALETTE["accent"], text_color="#000000",
                      hover_color=PALETTE["accent_dark"], font=_font(weight="bold"),
                      height=40, corner_radius=20, command=self._save).pack(side="right", expand=True, fill="x", padx=(8, 0))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        ctk.CTkLabel(self.body, text="Custom Model", font=_font(size=20, weight="bold"),
                     text_color=PALETTE["text_hi"]).pack(pady=(14, 10), anchor="w", padx=16)
        ctk.CTkLabel(self.body, text="Any OpenAI-compatible endpoint (Ollama, LM Studio, LiteLLM, vLLM, ...)",
                     font=_font(size=11), text_color=PALETTE["text_lo"], wraplength=380, justify="left",
                     anchor="w").pack(fill="x", padx=16, pady=(0, 10))

        self.name_entry = self._add_field("Display Name", "name", "My Local Llama")
        self.url_entry  = self._add_field("Base URL", "base_url", "http://localhost:11434/v1")
        self.key_entry  = self._add_field("API Key (optional)", "api_key", "Optional (leave empty for local servers)", show="•")
        self.id_entry   = self._add_field("Model ID", "model_id", "llama3.2")

    def _add_field(self, label, key, placeholder, show=None):
        ctk.CTkLabel(self.body, text=label, font=_font(size=12, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 4))
        kwargs = {"placeholder_text": placeholder, "height": 38, "corner_radius": 10,
                  "border_width": 0, "fg_color": PALETTE["bg_sidebar"]}
        if show: kwargs["show"] = show
        entry = ctk.CTkEntry(self.body, **kwargs)
        entry.insert(0, self.existing.get(key, ""))
        entry.pack(fill="x", padx=16)
        return entry

    def _save(self):
        data = {
            "name":     self.name_entry.get().strip(),
            "base_url": self.url_entry.get().strip().rstrip("/"),
            "api_key":  _clean_key(self.key_entry.get()),
            "model_id": self.id_entry.get().strip(),
        }
        if not (data["name"] and data["base_url"] and data["model_id"]):
            messagebox.showwarning("Missing Fields",
                                   "Display Name, Base URL and Model ID are required.", parent=self)
            return
        if not re.match(r"^https?://\S+$", data["base_url"], re.IGNORECASE):
            messagebox.showwarning("Invalid URL",
                                   "Base URL must start with http:// or https://", parent=self)
            return
        if self.callback(data) is False:
            return
        self.destroy()


def _clean_key(value):
    value = re.sub(r"[\s\u200b\u200c\u200d\u2060\ufeff]", "", value or "")
    value = value.strip("\"'")
    if value.startswith("ENTER_"):
        return ""
    return value


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(True, True)
        _center_on(self, parent, 620, 780); _make_modal(self, parent)
        self.minsize(*_fit_size(self, 560, 520))
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.bind("<Control-s>", lambda _e: self._save())
        self.bind("<Control-S>", lambda _e: self._save())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.configure(fg_color=PALETTE["bg_app"])
        self.app = app
        self.working_custom_models = [dict(c) for c in app.custom_models]
        self._initial_mode = app.appearance_mode
        self._initial_snapshot = None

        ctk.CTkLabel(self, text="Settings", font=_font(size=24, weight="bold"),
                     text_color=PALETTE["text_hi"]).pack(pady=(18, 8), anchor="w", padx=30)

        tabs = ctk.CTkTabview(
            self, fg_color=PALETTE["bg_app"], corner_radius=12,
            segmented_button_fg_color=PALETTE["bg_sidebar"],
            segmented_button_selected_color=PALETTE["bg_sidebar_2"],
            segmented_button_selected_hover_color=PALETTE["bg_sidebar_2"],
            segmented_button_unselected_color=PALETTE["bg_sidebar"],
            segmented_button_unselected_hover_color=PALETTE["bg_hover"],
            text_color=PALETTE["text_hi"], width=560, height=420,
        )
        self.tabs = tabs
        tabs.add("General"); tabs.add("Chat"); tabs.add("Appearance")
        tabs.add("API Keys"); tabs.add("Data"); tabs.add("About")

        # ============ GENERAL ============
        g = ctk.CTkScrollableFrame(tabs.tab("General"), fg_color="transparent")
        g.pack(fill="both", expand=True)

        ctk.CTkLabel(g, text="Profile", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 0))
        self.profile_entry = self._add_text_field(g, "Your Name", app.profile_name)

        ctk.CTkLabel(g, text="Defaults", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(16, 0))
        ctk.CTkLabel(g, text="Default Model", font=_font(size=12, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 4))
        self.default_model_selector = ctk.CTkOptionMenu(
            g, values=app._get_all_models(), height=38, corner_radius=10,
            fg_color=PALETTE["bg_sidebar"], button_color=PALETTE["bg_sidebar"],
            button_hover_color=PALETTE["bg_hover"], text_color=PALETTE["text_hi"],
        )
        self.default_model_selector.pack(fill="x", padx=16)
        self.default_model_selector.set(
            app.default_model if app.default_model in app._get_all_models() else BASE_MODELS[0])

        ctk.CTkLabel(g, text="Behavior", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(16, 4))
        self.enter_sends_var = self._add_switch(g, "Enter sends message (Ctrl+Enter always sends)", app.enter_sends)
        self.auto_scroll_var = self._add_switch(g, "Auto-scroll while streaming", app.auto_scroll)
        self.confirm_close_var = self._add_switch(g, "Confirm before closing", app.confirm_on_close)

        # ============ CHAT / GENERATION ============
        c = ctk.CTkScrollableFrame(tabs.tab("Chat"), fg_color="transparent")
        c.pack(fill="both", expand=True)

        ctk.CTkLabel(c, text="System Prompt", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 2))
        ctk.CTkLabel(c, text="Injected as system message on every request. Empty = no system message.",
                     font=_font(size=11), text_color=PALETTE["text_lo"],
                     anchor="w").pack(fill="x", padx=16, pady=(0, 6))
        self.preset_selector = ctk.CTkOptionMenu(
            c, values=list(SYSTEM_PROMPT_PRESETS), height=34, corner_radius=10,
            fg_color=PALETTE["bg_sidebar"], button_color=PALETTE["bg_sidebar"],
            button_hover_color=PALETTE["bg_hover"], text_color=PALETTE["text_hi"],
            font=_font(size=12), command=self._apply_preset,
        )
        self.preset_selector.pack(fill="x", padx=16, pady=(0, 6))
        self.preset_selector.set("— Select a preset —")
        self.system_prompt_box = ctk.CTkTextbox(
            c, height=100, corner_radius=10, border_width=0,
            fg_color=PALETTE["bg_sidebar"], text_color=PALETTE["text_hi"],
            font=_font(size=12), wrap="word",
        )
        self.system_prompt_box.pack(fill="x", padx=16)
        if app.system_prompt:
            self.system_prompt_box.insert("1.0", app.system_prompt)
        self.prompt_count_label = ctk.CTkLabel(c, text="", font=_font(size=10),
                                               text_color=PALETTE["text_lo"], anchor="e")
        self.prompt_count_label.pack(fill="x", padx=16)
        for ev in ("<KeyRelease>", "<<Paste>>", "<ButtonRelease-1>"):
            self.system_prompt_box.bind(ev, lambda _e: self.after(10, self._update_prompt_count), add="+")
        self._update_prompt_count()

        ctk.CTkLabel(c, text="Parameters", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(16, 4))
        self.temp_slider, _ = self._add_slider(c, "Temperature", app.temperature, 0.0, 2.0, 40)
        self.top_p_slider, _ = self._add_slider(c, "Top-P", app.top_p, 0.0, 1.0, 20)
        self.max_tokens_entry = self._add_text_field(
            c, "Max Tokens", str(app.max_tokens), hint="0 = provider default")
        self.history_entry = self._add_text_field(
            c, "History Limit", str(app.history_limit), hint="Max messages sent as context.")

        # ============ APPEARANCE ============
        a = ctk.CTkScrollableFrame(tabs.tab("Appearance"), fg_color="transparent")
        a.pack(fill="both", expand=True)

        ctk.CTkLabel(a, text="Theme Mode", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 4))
        self.theme_var = ctk.StringVar(value=app.appearance_mode.capitalize())
        theme_seg = ctk.CTkSegmentedButton(
            a, values=["Dark", "Light", "System"], variable=self.theme_var,
            fg_color=PALETTE["bg_sidebar"], unselected_color=PALETTE["bg_sidebar"],
            unselected_hover_color=PALETTE["bg_hover"], selected_color=PALETTE["bg_sidebar_2"],
            selected_hover_color=PALETTE["bg_hover"], text_color=PALETTE["text_hi"],
            font=_font(size=12), height=36, corner_radius=10,
        )
        theme_seg.pack(fill="x", padx=16)
        theme_seg.configure(command=lambda v: ctk.set_appearance_mode(v.lower()))

        ctk.CTkLabel(a, text="Accent Color", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(a, text="Theme previews instantly. Accent: send button updates now, the rest after restart.",
                     font=_font(size=11), text_color=PALETTE["text_lo"],
                     anchor="w").pack(fill="x", padx=16, pady=(0, 8))
        self.accent_var = ctk.StringVar(value=app.accent_color)
        accent_frame = ctk.CTkFrame(a, fg_color="transparent")
        accent_frame.pack(fill="x", padx=16)
        self.accent_buttons = []
        for hex_color in ACCENT_PRESETS:
            btn = ctk.CTkButton(
                accent_frame, text="", width=44, height=44, corner_radius=22,
                fg_color=hex_color, hover_color=hex_color,
                border_width=3 if hex_color == app.accent_color else 0,
                border_color=PALETTE["text_hi"],
                command=lambda cc=hex_color: self._select_accent(cc), text_color=PALETTE["text_hi"])
            btn.pack(side="left", padx=4)
            self.accent_buttons.append((hex_color, btn))

        ctk.CTkLabel(a, text="Chat Text", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(18, 0))
        self.font_slider, _ = self._add_slider(a, "Font Size", float(app.chat_font_size), 11, 20, 9,
                                               fmt="{:.0f}", on_change=self._update_font_preview)
        self.font_preview = ctk.CTkLabel(
            a, text="Preview: The quick brown fox — Hızlı kahverengi tilki",
            fg_color=PALETTE["bg_sidebar"], corner_radius=10, text_color=PALETTE["text_hi"],
            font=_font(size=app.chat_font_size), anchor="w", padx=12, pady=10)
        self.font_preview.pack(fill="x", padx=16, pady=(0, 8))

        # ============ API KEYS ============
        api_scroll = ctk.CTkScrollableFrame(tabs.tab("API Keys"), fg_color="transparent")
        api_scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(api_scroll, text="Provider API Keys", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 4))

        self.openai_entry      = self._add_key_field(api_scroll, "OpenAI API Key",      app.OPENAI_API_KEY)
        self.gemini_entry      = self._add_key_field(api_scroll, "Gemini API Key",      app.GEMINI_API_KEY)
        self.openrouter_entry  = self._add_key_field(api_scroll, "OpenRouter API Key",  app.OPENROUTER_API_KEY)
        self.groq_entry        = self._add_key_field(api_scroll, "Groq API Key",        app.GROQ_API_KEY)

        ctk.CTkFrame(api_scroll, fg_color=PALETTE["border"], height=1).pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(api_scroll, text="Custom Models", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(api_scroll, text="Add any OpenAI-compatible endpoint as a selectable model.",
                     font=_font(size=11), text_color=PALETTE["text_lo"],
                     anchor="w").pack(fill="x", padx=16, pady=(0, 8))
        self.custom_models_frame = ctk.CTkFrame(api_scroll, fg_color="transparent")
        self.custom_models_frame.pack(fill="x", padx=16, pady=(0, 6))
        self._render_custom_models()
        ctk.CTkButton(api_scroll, text="＋ Add Custom Model", height=36, corner_radius=10,
                      fg_color=PALETTE["bg_sidebar"], hover_color=PALETTE["bg_sidebar_2"],
                      text_color=PALETTE["text_hi"], font=_font(size=12),
                      command=self._add_custom_model).pack(fill="x", padx=16, pady=(4, 16))

        # ============ DATA ============
        d = ctk.CTkScrollableFrame(tabs.tab("Data"), fg_color="transparent")
        d.pack(fill="both", expand=True)

        ctk.CTkLabel(d, text="Storage", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 4))
        self.stats_label = ctk.CTkLabel(d, text="", font=_font(size=12), justify="left",
                                        text_color=PALETTE["text_mid"], anchor="w",
                                        fg_color=PALETTE["bg_sidebar"], corner_radius=10, padx=12, pady=10)
        self.stats_label.pack(fill="x", padx=16)
        self._refresh_stats()

        ctk.CTkLabel(d, text="Chats", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(16, 4))
        self._add_action(d, "⬇  Export all chats (JSON)", self._export_chats_json)
        self._add_action(d, "⬇  Export all chats (Markdown)", self._export_chats_md)
        self._add_action(d, "⬆  Import chats (JSON)", self._import_chats_json)
        self._add_action(d, "🗑  Delete all chats", self._delete_all_chats, danger=True)

        ctk.CTkLabel(d, text="Settings", font=_font(size=13, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(16, 4))
        self.include_keys_var = self._add_switch(d, "Include API keys when exporting settings (⚠ exported as plain text)", False)
        self._add_action(d, "⬇  Export settings", self._export_settings)
        self._add_action(d, "⬆  Import settings", self._import_settings)
        self._add_action(d, "↺  Reset to defaults (keeps API keys & custom models)",
                         self._reset_defaults, danger=True)

        # ============ ABOUT ============
        about_tab = tabs.tab("About")
        ctk.CTkLabel(about_tab, text="Project-Kizen", font=_font(size=15, weight="bold"),
                     text_color=PALETTE["text_hi"]).pack(pady=(18, 2))
        ctk.CTkLabel(about_tab, text="Multi-provider AI client.",
                     font=_font(size=12), text_color=PALETTE["text_mid"]).pack(pady=(0, 14))
        ctk.CTkLabel(about_tab, text="MIT License", font=_font(size=12, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(0, 6))
        license_box = ctk.CTkTextbox(about_tab, fg_color=PALETTE["bg_sidebar"],
                                     text_color=PALETTE["text_mid"], corner_radius=10,
                                     border_width=0, wrap="word",
                                     font=_font(family="Consolas", size=11))
        license_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        license_box.insert("1.0", LICENSE_TEXT)
        license_box.configure(state="disabled")

        # ============ BOTTOM BUTTONS ============
        self.status_label = ctk.CTkLabel(self, text="", font=_font(size=12), wraplength=560)
        self.status_label.pack(side="bottom", pady=(0, 8))
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=(8, 4), fill="x", padx=20)
        tabs.pack(pady=6, padx=20, fill="both", expand=True)
        self.after(0, lambda: setattr(self, "_initial_snapshot", self._snapshot()))
        self.test_btn = ctk.CTkButton(btn_frame, text="Test", fg_color=PALETTE["bg_sidebar"],
                                      hover_color=PALETTE["bg_sidebar_2"], height=40, corner_radius=20,
                                      command=self._test_connection, text_color=PALETTE["text_hi"])
        self.test_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="Save", fg_color=PALETTE["accent"], text_color="#000000",
                      hover_color=PALETTE["accent_dark"], font=_font(weight="bold"),
                      height=40, corner_radius=20,
                      command=self._save).pack(side="right", expand=True, fill="x", padx=(8, 0))

    def _snapshot(self):
        return (
            self.profile_entry.get(), self.default_model_selector.get(),
            self.enter_sends_var.get(), self.auto_scroll_var.get(), self.confirm_close_var.get(),
            self.system_prompt_box.get("1.0", "end").strip(),
            round(float(self.temp_slider.get()), 2), round(float(self.top_p_slider.get()), 2),
            self.max_tokens_entry.get(), self.history_entry.get(),
            self.theme_var.get(), self.accent_var.get(), int(round(self.font_slider.get())),
            self.openai_entry.get(), self.gemini_entry.get(),
            self.openrouter_entry.get(), self.groq_entry.get(),
            json.dumps(self.working_custom_models, sort_keys=True),
        )

    def _on_cancel(self):
        try:
            changed = self._snapshot() != self._initial_snapshot
        except Exception:
            changed = False
        if changed:
            ans = messagebox.askyesnocancel("Unsaved changes",
                                            "You have unsaved changes. Save them before closing?", parent=self)
            if ans is None: return
            if ans: self._save(); return
        try: ctk.set_appearance_mode(self._initial_mode)
        except Exception: pass
        self.destroy()

    def destroy(self):
        if getattr(self.app, "_settings_dialog", None) is self:
            self.app._settings_dialog = None
        try: self.grab_release()
        except Exception: pass
        super().destroy()

    # ---------- Field helpers ----------
    @staticmethod
    def _add_key_field(parent, label, value):
        ctk.CTkLabel(parent, text=label, font=_font(size=12, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(10, 4))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16)
        entry = ctk.CTkEntry(row, height=38, show="•", corner_radius=10,
                             border_width=0, fg_color=PALETTE["bg_sidebar"])
        entry.insert(0, value)
        entry.pack(side="left", fill="x", expand=True)

        def toggle():
            hidden = entry.cget("show") == "•"
            entry.configure(show="" if hidden else "•")
            eye.configure(text="🙈" if hidden else "👁")

        eye = ctk.CTkButton(row, text="👁", width=38, height=38, corner_radius=10,
                            fg_color=PALETTE["bg_sidebar"], hover_color=PALETTE["bg_hover"],
                            text_color=PALETTE["text_mid"], font=_font(size=14), command=toggle)
        eye.pack(side="right", padx=(6, 0))
        return entry

    def _add_action(self, parent, text, cmd, danger=False):
        ctk.CTkButton(parent, text=text, height=36, corner_radius=10, anchor="w",
                      fg_color=PALETTE["bg_sidebar"], hover_color=PALETTE["bg_sidebar_2"],
                      text_color=PALETTE["danger"] if danger else PALETTE["text_hi"],
                      font=_font(size=12), command=cmd).pack(fill="x", padx=16, pady=3)

    def _add_text_field(self, parent, label, value, hint=None, show=None):
        ctk.CTkLabel(parent, text=label, font=_font(size=12, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(fill="x", padx=16, pady=(8, 2))
        if hint:
            ctk.CTkLabel(parent, text=hint, font=_font(size=10),
                         text_color=PALETTE["text_lo"], anchor="w").pack(fill="x", padx=16, pady=(0, 4))
        kwargs = {"height": 38, "corner_radius": 10, "border_width": 0,
                  "fg_color": PALETTE["bg_sidebar"]}
        if show: kwargs["show"] = show
        entry = ctk.CTkEntry(parent, **kwargs)
        entry.insert(0, value)
        entry.pack(fill="x", padx=16, pady=(0, 4))
        return entry

    def _add_switch(self, parent, label, value):
        var = ctk.BooleanVar(value=value)
        sw = ctk.CTkSwitch(parent, text=label, variable=var,
                           font=_font(size=12), text_color=PALETTE["text_hi"],
                           progress_color=PALETTE["accent"],
                           fg_color=PALETTE["bg_sidebar"])
        sw.pack(fill="x", padx=16, pady=6)
        return var

    def _add_slider(self, parent, label, value, min_v, max_v, steps, fmt="{:.2f}", on_change=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkLabel(frame, text=label, font=_font(size=12, weight="bold"),
                     text_color=PALETTE["text_hi"], anchor="w").pack(side="left")
        value_label = ctk.CTkLabel(frame, text=fmt.format(value),
                                   font=_font(size=12), text_color=PALETTE["text_hi"])
        value_label.pack(side="right")
        slider = ctk.CTkSlider(parent, from_=min_v, to=max_v, number_of_steps=steps,
                               height=20, corner_radius=10,
                               fg_color=PALETTE["bg_sidebar"],
                               button_color=PALETTE["accent"],
                               progress_color=PALETTE["accent"])
        slider.pack(fill="x", padx=16, pady=(0, 8))
        slider.set(value)
        def _changed(v):
            value_label.configure(text=fmt.format(v))
            if on_change: on_change(v)
        slider.configure(command=_changed)
        return slider, value_label

    def _select_accent(self, hex_color):
        self.accent_var.set(hex_color)
        for c, btn in self.accent_buttons:
            btn.configure(border_width=3 if c == hex_color else 0)

    def _apply_preset(self, name):
        text = SYSTEM_PROMPT_PRESETS.get(name)
        if text is None: return
        current = self.system_prompt_box.get("1.0", "end").strip()
        if current and current != text:
            if not messagebox.askyesno(
                    "Overwrite prompt",
                    "Replace the current system prompt with this preset?",
                    parent=self):
                self.preset_selector.set("— Select a preset —")
                return
        self.system_prompt_box.delete("1.0", "end")
        if text: self.system_prompt_box.insert("1.0", text)
        self._update_prompt_count()
        self.preset_selector.set("— Select a preset —")

    def _update_prompt_count(self):
        text = self.system_prompt_box.get("1.0", "end").strip()
        self.prompt_count_label.configure(
            text=f"{len(text)} chars · ~{(len(text) + 3) // 4} tokens (estimate)")

    def _update_font_preview(self, v):
        self.font_preview.configure(font=_font(size=int(round(v))))

    # ---------- Data management ----------
    def _refresh_stats(self):
        app = self.app
        with app._db_lock:
            app.cursor.execute("SELECT COUNT(*) FROM sessions WHERE id IN (SELECT DISTINCT session_id FROM messages)")
            n_sessions = app.cursor.fetchone()[0]
            app.cursor.execute("SELECT COUNT(*) FROM messages")
            n_messages = app.cursor.fetchone()[0]
        try: size_kb = os.path.getsize(DB_PATH) / 1024
        except OSError: size_kb = 0
        size_txt = f"{size_kb / 1024:.2f} MB" if size_kb > 1024 else f"{size_kb:.1f} KB"
        self.stats_label.configure(
            text=f"Chats: {n_sessions}    Messages: {n_messages}    Database: {size_txt}\n"
                 f"Location: {os.path.abspath(DB_PATH)}")

    def _collect_chats(self):
        app = self.app
        with app._db_lock:
            app.cursor.execute(
                "SELECT s.id, s.title, s.created_at, m.sender, m.message, m.model "
                "FROM sessions s LEFT JOIN messages m ON m.session_id = s.id "
                "ORDER BY s.id ASC, m.id ASC")
            rows = app.cursor.fetchall()
        out, current, current_id = [], None, None
        for sid, title, created, sender, message, model in rows:
            if sid != current_id:
                current = {"title": title, "created_at": created, "messages": []}
                out.append(current)
                current_id = sid
            if sender is not None:
                current["messages"].append({"sender": sender, "message": message, "model": model})
        return [s for s in out if s["messages"]]

    def _ask_save(self, ext, title):
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        return filedialog.asksaveasfilename(parent=self, title=title, defaultextension=ext,
                                            initialfile=f"kizen_{stamp}{ext}",
                                            filetypes=[(ext.upper().strip("."), f"*{ext}"), ("All files", "*.*")])

    def _export_chats_json(self):
        path = self._ask_save(".json", "Export chats")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"app": "Project-Kizen", "version": 1, "sessions": self._collect_chats()},
                          f, ensure_ascii=False, indent=2)
            self._status(f"✓ Exported to {os.path.basename(path)}")
        except Exception as e:
            self._status(f"✗ Export failed: {e}", error=True)

    def _export_chats_md(self):
        path = self._ask_save(".md", "Export chats as Markdown")
        if not path: return
        try:
            lines = ["# Project-Kizen Chats", ""]
            for ses in self._collect_chats():
                lines += [f"## {ses['title']}", f"_{ses['created_at']}_", ""]
                for m in ses["messages"]:
                    if m["sender"] == "AI": who = f"AI ({m['model']})" if m["model"] else "AI"
                    else: who = m["sender"]
                    lines += [f"**{who}:**", "", m["message"], ""]
                lines += ["---", ""]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._status(f"✓ Exported to {os.path.basename(path)}")
        except Exception as e:
            self._status(f"✗ Export failed: {e}", error=True)

    def _import_chats_json(self):
        if self.app._is_responding:
            self._status("✗ Wait until the current response finishes.", error=True); return
        path = filedialog.askopenfilename(parent=self, title="Import chats",
                                          filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions = data.get("sessions") if isinstance(data, dict) else None
            if not isinstance(sessions, list):
                raise ValueError("Not a Project-Kizen chat export (missing 'sessions' list).")
            app = self.app
            with app._db_lock:
                app.cursor.execute(
                    "SELECT s.title, s.created_at, COUNT(m.id) FROM sessions s "
                    "LEFT JOIN messages m ON m.session_id = s.id GROUP BY s.id")
                existing = {}
                for t, c, n in app.cursor.fetchall():
                    existing.setdefault((t, c), set()).add(n)
            imported, skipped = 0, 0
            with app._db_lock:
              try:
                for ses in sessions:
                    if not isinstance(ses, dict): continue
                    msgs = [m for m in (ses.get("messages") or []) if isinstance(m, dict)]
                    if not msgs: continue
                    title = str(ses.get("title") or "Imported Chat")
                    created = str(ses.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M"))
                    key = (title, created)
                    if len(msgs) in existing.get(key, set()):
                        skipped += 1
                        continue
                    app.cursor.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)",
                                       (title, created))
                    sid = app.cursor.lastrowid
                    for m in msgs:
                        app.cursor.execute("INSERT INTO messages (session_id, sender, message, model) VALUES (?, ?, ?, ?)",
                                           (sid, str(m.get("sender") or "User"), str(m.get("message") or ""),
                                            str(m["model"]) if m.get("model") else None))
                    existing.setdefault(key, set()).add(len(msgs))
                    imported += 1
                app.conn.commit()
              except Exception:
                app.conn.rollback()
                raise
            app.load_sessions_list()
            self._refresh_stats()
            if imported or skipped:
                msg = f"✓ Imported {imported} chat(s)"
                if skipped: msg += f", skipped {skipped} duplicate(s)"
                self._status(msg)
            else:
                self._status("No chats found in file.", error=True)
        except Exception as e:
            self._status(f"✗ Import failed: {e}", error=True)

    def _delete_all_chats(self):
        app = self.app
        if app._is_responding:
            self._status("✗ Wait until the current response finishes.", error=True); return
        if not messagebox.askyesno("Delete all chats",
                                   "This permanently deletes ALL chats. Continue?", parent=self):
            return
        with app._db_lock:
            app.cursor.execute("DELETE FROM messages")
            app.cursor.execute("DELETE FROM sessions")
            app.conn.commit()
        vacuum_err = None
        try:
            tmp = sqlite3.connect(DB_PATH, isolation_level=None)
            try: tmp.execute("VACUUM")
            finally: tmp.close()
        except Exception as e:
            vacuum_err = e
        app._create_new_chat_internal()
        self._refresh_stats()
        if vacuum_err:
            self._status(f"✓ Chats deleted (VACUUM failed: {vacuum_err})")
        else:
            self._status("✓ All chats deleted")

    def _export_settings(self):
        path = self._ask_save(".json", "Export settings")
        if not path: return
        try:
            data = self.app._config_dict()
            if not self.include_keys_var.get():
                for k in ("openai_key", "gemini_key", "openrouter_key", "groq_key"):
                    data.pop(k, None)
                data["custom_models"] = [{**c, "api_key": ""} for c in data.get("custom_models", [])]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._status(f"✓ Settings exported to {os.path.basename(path)}")
        except Exception as e:
            self._status(f"✗ Export failed: {e}", error=True)

    def _import_settings(self):
        path = filedialog.askopenfilename(parent=self, title="Import settings",
                                          filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path: return
        if not messagebox.askyesno(
                "Import settings",
                "This will overwrite your current settings.\n"
                "API keys and custom models that are empty in the file will be preserved.\n\n"
                "Continue?",
                parent=self):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict): raise ValueError("Invalid settings file.")
            cfg = self.app._config_dict()
            skipped = []
            if "model" in data and "default_model" not in data and isinstance(data["model"], str):
                data = dict(data)
                data["default_model"] = data["model"]
            for key, val in data.items():
                if key not in cfg:
                    continue
                if key == "custom_models":
                    if not isinstance(val, list):
                        skipped.append(key); continue
                    clean = self.app._sanitize_config({key: val})[key]
                    if not clean:
                        if val: skipped.append(key)
                        continue
                    old = {c["name"]: c for c in cfg["custom_models"]}
                    for c in clean:
                        if not c["api_key"] and c["name"] in old:
                            c["api_key"] = old[c["name"]].get("api_key", "")
                    cfg[key] = clean
                    continue
                if key.endswith("_key") and val == "":
                    continue
                san = self.app._sanitize_config({key: val}).get(key)
                if self._accept_import_value(val, san):
                    cfg[key] = san
                else:
                    skipped.append(key)
            msg = "✓ Settings imported" + (f" (skipped invalid: {', '.join(skipped)})" if skipped else "")
            self._apply_and_reopen(cfg, msg)
        except Exception as e:
            self._status(f"✗ Import failed: {e}", error=True)

    @staticmethod
    def _accept_import_value(val, sanitized):
        """OPT: extracted from inline logic — accept numeric strings and case-insensitive matches."""
        if sanitized == val:
            return True
        try:
            if isinstance(sanitized, float) and float(val) == sanitized: return True
            if isinstance(sanitized, int) and not isinstance(sanitized, bool) and int(val) == sanitized: return True
        except (TypeError, ValueError):
            pass
        if isinstance(val, str) and isinstance(sanitized, str):
            return sanitized.lower() == val.strip().lower()
        return False

    def _reset_defaults(self):
        if not messagebox.askyesno("Reset", "Reset all settings to defaults?\n"
                                   "API keys and custom models will be kept.", parent=self):
            return
        cfg = self.app._config_dict()
        cfg.update(DEFAULT_SETTINGS)
        self._apply_and_reopen(cfg, "✓ Settings reset")

    def _apply_and_reopen(self, cfg, msg):
        app = self.app
        old_default, old_font = app.default_model, app.chat_font_size
        app._apply_config_values(cfg)
        app.profile_btn.configure(text=f"👤  {app.profile_name}")
        app._refresh_model_selectors()
        if app.default_model != old_default and not app._is_responding:
            target = app.default_model if app.default_model in app._get_all_models() else BASE_MODELS[0]
            app.chat_model_selector.set(target)
            app.welcome_model_selector.set(target)
        saved = app.save_config()
        app._apply_live_style()
        font_changed = app.chat_font_size != old_font
        self.destroy()
        if font_changed and not app._is_responding and app.current_session_id:
            app.load_session(app.current_session_id)
        if not saved:
            msg = "⚠ " + msg.replace("✓", "").strip() + " — but config file could not be written"
        app._toast.show(msg)
        app.after_idle(app.open_settings_dialog)

    def _status(self, text, error=False):
        self.status_label.configure(text=text, text_color=PALETTE["danger"] if error else PALETTE["success"])

    # ---------- Custom model management ----------
    def _render_custom_models(self):
        if hasattr(self, "default_model_selector"):
            values = BASE_MODELS + [c["name"] for c in self.working_custom_models]
            self.default_model_selector.configure(values=values)
            if self.default_model_selector.get() not in values:
                fallback = self.app.default_model if self.app.default_model in values else BASE_MODELS[0]
                self.default_model_selector.set(fallback)
        for w in self.custom_models_frame.winfo_children():
            w.destroy()
        if not self.working_custom_models:
            ctk.CTkLabel(self.custom_models_frame, text="No custom models yet.",
                         font=_font(size=11),
                         text_color=PALETTE["text_lo"]).pack(pady=6, anchor="w")
            return
        for i, cm in enumerate(self.working_custom_models):
            row = ctk.CTkFrame(self.custom_models_frame, fg_color=PALETTE["bg_sidebar"], corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=cm["name"], font=_font(size=12),
                         text_color=PALETTE["text_hi"], anchor="w").pack(
                side="left", padx=10, pady=6, fill="x", expand=True)
            ctk.CTkButton(row, text="✏️", width=28, height=28, corner_radius=6,
                          fg_color="transparent", hover_color=PALETTE["bg_hover"],
                          font=_font(size=11),
                          command=lambda idx=i: self._edit_custom_model(idx), text_color=PALETTE["text_hi"]).pack(
                side="right", padx=(0, 4), pady=4)
            ctk.CTkButton(row, text="🗑", width=28, height=28, corner_radius=6,
                          fg_color="transparent", hover_color=PALETTE["bg_hover"],
                          font=_font(size=11), text_color=PALETTE["danger"],
                          command=lambda idx=i: self._delete_custom_model(idx)).pack(
                side="right", pady=4)

    def _custom_dialog_parent(self):
        dlg = getattr(self, "_custom_dialog", None)
        try:
            if dlg is not None and dlg.winfo_exists(): return dlg
        except tk.TclError:
            pass
        return self

    def _open_custom_dialog(self, cb, existing=None):
        dlg = getattr(self, "_custom_dialog", None)
        try:
            if dlg is not None and dlg.winfo_exists():
                dlg.lift(); dlg.focus_force()
                return
        except tk.TclError:
            pass
        self._custom_dialog = CustomModelDialog(self, cb, existing=existing)

    def _add_custom_model(self):
        def cb(data):
            if data["name"] in BASE_MODELS or any(c["name"] == data["name"] for c in self.working_custom_models):
                messagebox.showerror("Duplicate Name",
                                     f"A model named '{data['name']}' already exists.",
                                     parent=self._custom_dialog_parent())
                return False
            self.working_custom_models.append(data)
            self._render_custom_models()
            return True
        self._open_custom_dialog(cb)

    def _edit_custom_model(self, idx):
        existing = self.working_custom_models[idx]
        def cb(data):
            if data["name"] in BASE_MODELS or any(
                c["name"] == data["name"] for c in self.working_custom_models if c is not existing
            ):
                messagebox.showerror("Duplicate Name",
                                     f"A model named '{data['name']}' already exists.",
                                     parent=self._custom_dialog_parent())
                return False
            old_name = existing["name"]
            self.working_custom_models[idx] = data
            if self.default_model_selector.get() == old_name:
                self.default_model_selector.set(data["name"])
            self._render_custom_models()
            return True
        self._open_custom_dialog(cb, existing=existing)

    def _delete_custom_model(self, idx):
        name = self.working_custom_models[idx]["name"]
        if messagebox.askyesno("Delete", f"Remove custom model '{name}'?", parent=self):
            self.working_custom_models.pop(idx)
            self._render_custom_models()

    # ---------- Test / Save ----------
    def _test_connection(self):
        if getattr(self, "_testing", False): return
        self._testing = True
        self.test_btn.configure(state="disabled", text="Testing...")
        self.status_label.configure(text="Testing connections...", text_color=PALETTE["text_mid"])
        providers = [
            ("OpenAI",     self.openai_entry,     None),
            ("Gemini",     self.gemini_entry,     "genai"),
            ("OpenRouter", self.openrouter_entry, "https://openrouter.ai/api/v1"),
            ("Groq",       self.groq_entry,       "https://api.groq.com/openai/v1"),
        ]
        jobs = []
        for name, entry, base_url in providers:
            key = _clean_key(entry.get())
            if key:
                jobs.append((name, key, base_url))
        for cm in self.working_custom_models:
            key = (cm.get("api_key") or "").strip() or "no-key"
            jobs.append((cm["name"], key, cm.get("base_url", "")))
        if not jobs:
            self._testing = False
            self.test_btn.configure(state="normal", text="Test")
            self._status("No API keys to test.", error=True)
            return

        def worker():
            ok, failed = [], []
            for name, key, base_url in jobs:
                start = time.monotonic()
                try:
                    if base_url == "genai":
                        try:
                            from google.genai import types as _genai_types
                            client = genai.Client(api_key=key,
                                                  http_options=_genai_types.HttpOptions(timeout=10_000))
                        except Exception:
                            client = genai.Client(api_key=key)
                        next(iter(client.models.list()), None)
                    elif base_url:
                        OpenAI(api_key=key, base_url=base_url, timeout=10, max_retries=0).models.list()
                    else:
                        OpenAI(api_key=key, timeout=10, max_retries=0).models.list()
                    ok.append(f"{name} ({int((time.monotonic() - start) * 1000)} ms)")
                except Exception:
                    failed.append(name)
            self.app._post_ui(self._on_test_done, ok, failed)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, ok, failed):
        self._testing = False
        try:
            if not self.winfo_exists(): return
        except tk.TclError:
            return
        self.test_btn.configure(state="normal", text="Test")
        parts = []
        if ok: parts.append("✓ " + ", ".join(ok))
        if failed: parts.append("✗ Failed: " + ", ".join(failed))
        self.status_label.configure(text="\n".join(parts), wraplength=560,
                                    text_color=PALETTE["danger"] if failed else PALETTE["success"])

    def _save(self):
        try:
            if int(self.max_tokens_entry.get().strip() or "0") < 0 or int(self.history_entry.get().strip() or "40") < 1:
                raise ValueError
        except ValueError:
            self.tabs.set("Chat")
            self._status("✗ Max Tokens must be ≥ 0 and History Limit ≥ 1 (whole numbers).", error=True)
            return

        if self.profile_entry.get().strip().upper() == "AI":
            self.tabs.set("General")
            self._status("✗ 'AI' is reserved for the assistant - choose another profile name.", error=True)
            return

        new_profile = self.profile_entry.get().strip()
        if new_profile and new_profile != self.app.profile_name:
            self.app.profile_name = new_profile
            self.app.profile_btn.configure(text=f"👤  {new_profile}")

        all_names = BASE_MODELS + [c["name"] for c in self.working_custom_models]
        chosen = self.default_model_selector.get()
        old_default = self.app.default_model
        self.app.default_model = chosen if chosen in all_names else BASE_MODELS[0]
        default_changed = self.app.default_model != old_default
        self.app.enter_sends = self.enter_sends_var.get()
        self.app.auto_scroll = self.auto_scroll_var.get()
        self.app.confirm_on_close = self.confirm_close_var.get()

        self.app.system_prompt = self.system_prompt_box.get("1.0", "end").strip()
        self.app.temperature = round(float(self.temp_slider.get()), 2)
        self.app.top_p = round(float(self.top_p_slider.get()), 2)
        max_tokens = min(int(self.max_tokens_entry.get().strip() or "0"), 1_000_000)
        history_limit = int(self.history_entry.get().strip() or "40")
        history_clamped = history_limit > 500
        self.app.max_tokens = max_tokens
        self.app.history_limit = min(history_limit, 500)

        new_mode = self.theme_var.get().lower()
        self.app.appearance_mode = new_mode
        try: ctk.set_appearance_mode(new_mode)
        except Exception: pass

        new_accent = self.accent_var.get()
        if new_accent != self.app.accent_color:
            self.app.accent_color = new_accent
            PALETTE["accent"] = new_accent
            PALETTE["accent_dark"] = _darken(new_accent)

        new_font = int(round(self.font_slider.get()))
        font_changed = new_font != self.app.chat_font_size
        self.app.chat_font_size = new_font
        CHAT_STYLE["size"] = new_font

        self.app.OPENAI_API_KEY = _clean_key(self.openai_entry.get())
        self.app.GEMINI_API_KEY = _clean_key(self.gemini_entry.get())
        self.app.OPENROUTER_API_KEY = _clean_key(self.openrouter_entry.get())
        self.app.GROQ_API_KEY = _clean_key(self.groq_entry.get())
        self.app.custom_models = [dict(c) for c in self.working_custom_models]

        self.app._refresh_model_selectors()
        if default_changed and not self.app._is_responding:
            self.app.chat_model_selector.set(self.app.default_model)
            self.app.welcome_model_selector.set(self.app.default_model)
        saved = self.app.save_config()
        self.app._apply_live_style()
        if font_changed and not self.app._is_responding and self.app.current_session_id:
            self.app.load_session(self.app.current_session_id)
        if not saved:
            self.app._toast.show("✗ Settings saved to memory, but could not write config file")
        elif history_clamped:
            self.app._toast.show("✓ Settings saved (History Limit capped to 500)")
        else:
            self.app._toast.show("✓ Settings saved")
        self.destroy()


# ============================================================
# MAIN APPLICATION
# ============================================================
class ProjectKizenClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Project-Kizen")
        w, h = _fit_size(self, 1280, 800)
        self.geometry(f"{w}x{h}")
        self.minsize(*_fit_size(self, 1000, 700))
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_session_id = None
        self.sidebar_expanded = True
        self._is_responding = False
        self._db_lock = threading.Lock()
        self._ui_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._current_bubble = None
        self._worker = None
        self._prompt_history = []

        self._apply_config_values(self._load_config())
        self.configure(fg_color=PALETTE["bg_app"])

        initial_model = self.default_model
        if initial_model not in BASE_MODELS and not any(c["name"] == initial_model for c in self.custom_models):
            initial_model = BASE_MODELS[0]

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

    def _apply_config_values(self, cfg):
        cfg = self._sanitize_config(cfg)
        self.OPENAI_API_KEY     = cfg.get("openai_key",     "ENTER_OPENAI_API_KEY_HERE")
        self.GEMINI_API_KEY     = cfg.get("gemini_key",     "ENTER_GEMINI_API_KEY_HERE")
        self.OPENROUTER_API_KEY = cfg.get("openrouter_key", "ENTER_OPENROUTER_API_KEY_HERE")
        self.GROQ_API_KEY       = cfg.get("groq_key",       "ENTER_GROQ_API_KEY_HERE")
        self.custom_models      = cfg.get("custom_models", [])

        self.profile_name     = cfg.get("profile", "Admin")
        self.default_model    = cfg.get("default_model", cfg.get("model", "Gemini 2.5 Flash"))
        _known = BASE_MODELS + [c["name"] for c in self.custom_models]
        if self.default_model not in _known:
            self.default_model = BASE_MODELS[0]
        self.enter_sends      = cfg.get("enter_sends", True)
        self.auto_scroll      = cfg.get("auto_scroll", True)
        self.confirm_on_close = cfg.get("confirm_on_close", True)

        self.temperature    = float(cfg.get("temperature", 0.7))
        self.max_tokens     = int(cfg.get("max_tokens", 0))
        self.top_p          = float(cfg.get("top_p", 1.0))
        self.system_prompt  = cfg.get("system_prompt", "")
        self.history_limit  = int(cfg.get("history_limit", HISTORY_LIMIT))
        self.chat_font_size = int(cfg.get("chat_font_size", 14))
        CHAT_STYLE["size"]  = self.chat_font_size

        self.appearance_mode = cfg.get("appearance_mode", "dark")
        self.accent_color    = cfg.get("accent_color", "#A8C7FA")
        PALETTE["accent"] = self.accent_color
        PALETTE["accent_dark"] = _darken(self.accent_color)
        try: ctk.set_appearance_mode(self.appearance_mode)
        except Exception: pass

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f: data = json.load(f)
            if not isinstance(data, dict): raise ValueError("config is not a JSON object")
            return data
        except FileNotFoundError:
            return {}
        except Exception:
            try: os.replace(CONFIG_PATH, CONFIG_PATH + ".bak")
            except OSError: pass
            return {}

    @staticmethod
    def _sanitize_config(cfg):
        cfg = dict(cfg) if isinstance(cfg, dict) else {}
        def num(key, cast, lo, hi, default):
            try: cfg[key] = min(hi, max(lo, cast(cfg.get(key, default))))
            except (TypeError, ValueError, OverflowError): cfg[key] = default
        num("temperature", float, 0.0, 2.0, 0.7)
        num("top_p", float, 0.0, 1.0, 1.0)
        num("max_tokens", int, 0, 1_000_000, 0)
        num("history_limit", int, 1, 500, HISTORY_LIMIT)
        num("chat_font_size", int, 11, 20, 14)
        for key, default in (("enter_sends", True), ("auto_scroll", True), ("confirm_on_close", True)):
            if not isinstance(cfg.get(key, default), bool): cfg[key] = default
        for key in ("profile", "system_prompt", "default_model", "model",
                    "openai_key", "gemini_key", "openrouter_key", "groq_key"):
            if key in cfg and not isinstance(cfg[key], str): cfg.pop(key)
        if "profile" in cfg:
            prof = cfg["profile"].strip()
            if prof and prof.upper() != "AI": cfg["profile"] = prof
            else: cfg.pop("profile")
        if str(cfg.get("appearance_mode", "dark")).lower() not in ("dark", "light", "system"):
            cfg["appearance_mode"] = "dark"
        else:
            cfg["appearance_mode"] = str(cfg.get("appearance_mode", "dark")).lower()
        acc = cfg.get("accent_color", "#A8C7FA")
        if not (isinstance(acc, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", acc)):
            cfg["accent_color"] = "#A8C7FA"
        cms = cfg.get("custom_models", [])
        clean, seen = [], set(BASE_MODELS)
        for c in (cms if isinstance(cms, list) else []):
            if not isinstance(c, dict): continue
            item = {k: str(c.get(k) or "").strip() for k in ("name", "base_url", "api_key", "model_id")}
            item["base_url"] = item["base_url"].rstrip("/")
            item["api_key"] = _clean_key(item["api_key"])
            if not (item["name"] and item["model_id"]
                    and re.match(r"^https?://\S+$", item["base_url"], re.IGNORECASE)):
                continue
            if item["name"] in seen:
                continue
            seen.add(item["name"])
            clean.append(item)
        cfg["custom_models"] = clean
        return cfg

    def _config_dict(self):
        model = self.chat_model_selector.get() if hasattr(self, "chat_model_selector") else self.default_model
        return {
                "openai_key":       self.OPENAI_API_KEY,
                "gemini_key":       self.GEMINI_API_KEY,
                "openrouter_key":   self.OPENROUTER_API_KEY,
                "groq_key":         self.GROQ_API_KEY,
                "profile":          self.profile_name,
                "model":            model,
                "default_model":    self.default_model,
                "enter_sends":      self.enter_sends,
                "auto_scroll":      self.auto_scroll,
                "confirm_on_close": self.confirm_on_close,
                "temperature":      self.temperature,
                "max_tokens":       self.max_tokens,
                "top_p":            self.top_p,
                "system_prompt":    self.system_prompt,
                "history_limit":    self.history_limit,
                "appearance_mode":  self.appearance_mode,
                "accent_color":     self.accent_color,
                "chat_font_size":   self.chat_font_size,
                "custom_models":    self.custom_models,
            }

    def save_config(self):
        tmp = CONFIG_PATH + ".tmp"
        try:
            data = self._config_dict()
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            try: os.chmod(tmp, 0o600)
            except OSError: pass
            os.replace(tmp, CONFIG_PATH)
            return True
        except Exception:
            traceback.print_exc()
            try: os.remove(tmp)
            except OSError: pass
            return False

    def _apply_live_style(self):
        if not self._is_responding:
            self.send_btn.configure(fg_color=PALETTE["accent"], hover_color=PALETTE["accent_dark"])

    def _get_all_models(self):
        return BASE_MODELS + [cm["name"] for cm in self.custom_models]

    def _refresh_model_selectors(self):
        all_models = self._get_all_models()
        self.chat_model_selector.configure(values=all_models)
        self.welcome_model_selector.configure(values=all_models)
        if self.default_model not in all_models:
            self.default_model = all_models[0]
        fallback = self.default_model
        if self.chat_model_selector.get() not in all_models:
            self.chat_model_selector.set(fallback)
        if self.welcome_model_selector.get() not in all_models:
            self.welcome_model_selector.set(fallback)

    # ---------------------------------------------------------
    # SIDEBAR (Expanded)
    # ---------------------------------------------------------
    def _build_expanded_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=PALETTE["bg_sidebar"])
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(2, weight=1)
        self.sidebar_frame.grid_propagate(False)

        top_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        ctk.CTkLabel(top_frame, text="⚡ Project-Kizen", font=_font(size=18, weight="bold"),
                     text_color=PALETTE["text_hi"]).pack(side="left")
        collapse_btn = ctk.CTkButton(top_frame, text="◫", width=36, height=36, corner_radius=18,
                                     fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"],
                                     text_color=PALETTE["text_mid"], font=_font(size=18),
                                     command=self.toggle_sidebar)
        collapse_btn.pack(side="right")
        ToolTip(collapse_btn, "Close sidebar")

        menu_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        menu_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self._add_menu_btn(menu_frame, "✏️", "New chat", self.create_new_chat)

        hist_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        hist_frame.grid(row=2, column=0, sticky="nsew", padx=10)
        ctk.CTkLabel(hist_frame, text="All", font=_font(size=11, weight="bold"),
                     text_color=PALETTE["text_lo"], anchor="w").pack(fill="x", padx=10, pady=(10, 4))
        self.history_scroll_frame = ctk.CTkScrollableFrame(hist_frame, fg_color="transparent")
        self.history_scroll_frame.pack(fill="both", expand=True)

        bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=15, pady=15)
        self.profile_btn = ctk.CTkButton(bottom_frame, text=f"👤  {self.profile_name}",
                                         height=40, corner_radius=20, fg_color="transparent",
                                         hover_color=PALETTE["bg_sidebar_2"], anchor="w",
                                         font=_font(size=13, weight="bold"),
                                         text_color=PALETTE["text_mid"], command=self.open_profile_dialog)
        self.profile_btn.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(bottom_frame, text="⚙️", width=40, height=40, corner_radius=20,
                      fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"],
                      font=_font(size=18), text_color=PALETTE["text_mid"],
                      command=self.open_settings_dialog).pack(side="right")

    def _add_menu_btn(self, parent, icon, text, cmd):
        btn = ctk.CTkButton(parent, text=f"{icon}  {text}", height=40, corner_radius=20,
                            fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"],
                            anchor="w", font=_font(size=13),
                            text_color=PALETTE["text_hi"], command=cmd)
        btn.pack(fill="x", pady=1)

    # ---------------------------------------------------------
    # SIDEBAR (Collapsed)
    # ---------------------------------------------------------
    def _build_collapsed_sidebar(self):
        self.icon_frame = ctk.CTkFrame(self, width=70, corner_radius=0, fg_color=PALETTE["bg_sidebar"])
        top_frame = ctk.CTkFrame(self.icon_frame, fg_color="transparent")
        top_frame.pack(fill="x", pady=15)
        expand_btn = ctk.CTkButton(top_frame, text="◫", width=44, height=44, corner_radius=22,
                                   fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"],
                                   text_color=PALETTE["text_mid"], font=_font(size=18),
                                   command=self.toggle_sidebar)
        expand_btn.pack()
        ToolTip(expand_btn, "Open sidebar")

        def add_icon(icon, tooltip, cmd):
            btn = ctk.CTkButton(self.icon_frame, text=icon, width=44, height=44, corner_radius=22,
                                fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"],
                                font=_font(size=18), text_color=PALETTE["text_hi"], command=cmd)
            btn.pack(pady=8)
            ToolTip(btn, tooltip)

        add_icon("✏️", "New chat", self.create_new_chat)

        bottom_frame = ctk.CTkFrame(self.icon_frame, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=15)
        set_btn = ctk.CTkButton(bottom_frame, text="⚙️", width=44, height=44, corner_radius=22,
                                fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"],
                                font=_font(size=18), text_color=PALETTE["text_mid"],
                                command=self.open_settings_dialog)
        set_btn.pack()
        ToolTip(set_btn, "Settings")
        prof_btn = ctk.CTkButton(bottom_frame, text="👤", width=44, height=44, corner_radius=22,
                                 fg_color="transparent", hover_color=PALETTE["bg_sidebar_2"],
                                 font=_font(size=18), text_color=PALETTE["text_mid"],
                                 command=self.open_profile_dialog)
        prof_btn.pack(pady=(8, 0))
        ToolTip(prof_btn, "Account")

    # ---------------------------------------------------------
    # MAIN AREA
    # ---------------------------------------------------------
    def _build_main_area(self, initial_model):
        all_models = self._get_all_models()
        if initial_model not in all_models:
            initial_model = all_models[0]

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=60)
        self.top_bar.grid(row=0, column=0, sticky="ew")
        self.top_bar.grid_propagate(False)
        self._top_title = ctk.CTkLabel(self.top_bar, text="New Chat",
                                       font=_font(size=18, weight="bold"),
                                       text_color=PALETTE["text_hi"])
        self._top_title.pack(side="left", padx=20, pady=20)

        self.center_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.center_frame.grid(row=1, column=0, sticky="nsew")
        self.center_frame.grid_rowconfigure(0, weight=1)
        self.center_frame.grid_columnconfigure(0, weight=1)

        self.welcome_frame = ctk.CTkFrame(self.center_frame, fg_color="transparent")
        self.welcome_frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkFrame(self.welcome_frame, fg_color="transparent", height=180).pack()
        ctk.CTkLabel(self.welcome_frame, text="⚡", font=_font(size=50),
                     text_color=PALETTE["accent"]).pack()
        ctk.CTkLabel(self.welcome_frame, text="Where should we start?",
                     font=_font(family="Segoe UI", size=36),
                     text_color=PALETTE["text_mid"]).pack(pady=(10, 40))

        self.welcome_input_frame = ctk.CTkFrame(self.welcome_frame, fg_color=PALETTE["bg_input"],
                                                corner_radius=30, height=60)
        self.welcome_input_frame.pack(fill="x", padx=180)
        self.welcome_plus_btn = ctk.CTkButton(self.welcome_input_frame, text="＋", width=40, height=40, corner_radius=20,
                      fg_color="transparent", hover_color=PALETTE["bg_hover"],
                      font=_font(size=20), text_color=PALETTE["text_hi"],
                      command=lambda: self._show_prompt_history(self.welcome_plus_btn, self.welcome_entry))
        self.welcome_plus_btn.pack(side="left", anchor="s", padx=10, pady=(0, 12))
        self.welcome_entry = self._make_text_input(self.welcome_input_frame, "Ask Project-Kizen")
        self.welcome_entry.pack(side="left", fill="both", expand=True, padx=5, pady=8)
        self.welcome_entry.bind("<Return>", lambda e: self._on_textbox_key(e, self.welcome_entry, self._send_from_welcome))
        self.welcome_entry.bind("<Control-Return>", lambda e: (self._send_from_welcome(), "break")[1])
        self.welcome_model_selector = ctk.CTkOptionMenu(
            self.welcome_input_frame, values=all_models, width=160, height=36, corner_radius=18,
            fg_color=PALETTE["bg_input"], button_color=PALETTE["bg_input"],
            button_hover_color=PALETTE["bg_hover"], text_color=PALETTE["text_hi"],
            font=_font(size=12), command=self._on_welcome_model_change)
        self.welcome_model_selector.pack(side="right", anchor="s", padx=10, pady=(0, 12))
        self.welcome_model_selector.set(initial_model)

        self.chat_scroll = ctk.CTkScrollableFrame(self.center_frame, fg_color="transparent")
        self.chat_scroll.grid(row=0, column=0, sticky="nsew")

        self.chat_input_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.chat_input_container.grid(row=2, column=0, sticky="ew", padx=180, pady=(0, 30))
        self.chat_input_frame = ctk.CTkFrame(self.chat_input_container, fg_color=PALETTE["bg_input"],
                                             corner_radius=30, height=60)
        self.chat_input_frame.pack(fill="x")
        self.plus_btn = ctk.CTkButton(self.chat_input_frame, text="＋", width=40, height=40, corner_radius=20,
                      fg_color="transparent", hover_color=PALETTE["bg_hover"],
                      font=_font(size=20), text_color=PALETTE["text_hi"],
                      command=self._show_prompt_history)
        self.plus_btn.pack(side="left", anchor="s", padx=10, pady=(0, 12))
        self.prompt_entry = self._make_text_input(self.chat_input_frame, "Ask Project-Kizen")
        self.prompt_entry.pack(side="left", fill="both", expand=True, padx=5, pady=8)
        self.prompt_entry.bind("<Return>", self._on_enter_key)
        self.prompt_entry.bind("<Control-Return>", lambda e: (self.send_message(), "break")[1])
        self.send_btn = ctk.CTkButton(self.chat_input_frame, text="↑", width=40, height=40,
                                      corner_radius=20, fg_color=PALETTE["accent"],
                                      hover_color=PALETTE["accent_dark"],
                                      font=_font(size=18, weight="bold"),
                                      text_color="#000000", command=self.send_message)
        self.send_btn.pack(side="right", anchor="s", padx=10, pady=(0, 12))
        self.chat_model_selector = ctk.CTkOptionMenu(
            self.chat_input_frame, values=all_models, width=160, height=36, corner_radius=18,
            fg_color=PALETTE["bg_input"], button_color=PALETTE["bg_input"],
            button_hover_color=PALETTE["bg_hover"], text_color=PALETTE["text_hi"],
            font=_font(size=12), command=self._on_model_change)
        self.chat_model_selector.pack(side="right", anchor="s", padx=10, pady=(0, 12))
        self.chat_model_selector.set(initial_model)

        self.model_selector = self.chat_model_selector

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

    # OPT: single helper for both selector changes
    def _sync_and_save_model(self, source, target):
        target.set(source.get())
        if not self.save_config():
            self._toast.show("✗ Model selected but config could not be saved")

    def _on_model_change(self, _val=None):
        self._sync_and_save_model(self.chat_model_selector, self.welcome_model_selector)

    def _on_welcome_model_change(self, _val=None):
        self._sync_and_save_model(self.welcome_model_selector, self.chat_model_selector)

    def _send_from_welcome(self):
        if self._is_responding:
            return
        if getattr(self.welcome_entry, "_placeholder_active", False):
            return
        text = self.welcome_entry.get("1.0", "end-1c").strip()
        if not text:
            return
        self.prompt_entry._placeholder_active = False
        self.prompt_entry.configure(text_color=PALETTE["text_hi"])
        self.prompt_entry.delete("1.0", "end")
        self.prompt_entry.insert("1.0", text)
        self.send_message()

    def create_new_chat(self):
        if self._is_responding: return
        self._create_new_chat_internal()

    def _create_new_chat_internal(self):
        if self.current_session_id is not None:
            with self._db_lock:
                self.cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?",
                                    (self.current_session_id,))
                if self.cursor.fetchone()[0] == 0:
                    self.cursor.execute("DELETE FROM sessions WHERE id = ?", (self.current_session_id,))
                    self.conn.commit()
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
            self.top_bar.grid_remove(); self.chat_scroll.grid_remove(); self.chat_input_container.grid_remove()
            self.welcome_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.welcome_frame.grid_remove()
            self.top_bar.grid(row=0, column=0, sticky="ew")
            self.chat_scroll.grid(row=0, column=0, sticky="nsew")
            self.chat_input_container.grid(row=2, column=0, sticky="ew", padx=180, pady=(0, 30))

    def load_sessions_list(self, filter_text=""):
        for widget in self.history_scroll_frame.winfo_children(): widget.destroy()
        with self._db_lock:
            if filter_text:
                self.cursor.execute(
                    "SELECT id, title, created_at FROM sessions WHERE LOWER(title) LIKE ? ORDER BY id DESC",
                    (f"%{filter_text.lower()}%",))
            else:
                self.cursor.execute("SELECT id, title, created_at FROM sessions ORDER BY id DESC")
            sessions = self.cursor.fetchall()
        for sid, title, c_at in sessions: self._build_session_row(sid, title)

    def _build_session_row(self, session_id, title):
        is_active = (session_id == self.current_session_id)
        row = ctk.CTkFrame(self.history_scroll_frame,
                           fg_color=PALETTE["bg_sidebar_2"] if is_active else "transparent",
                           corner_radius=20)
        row.pack(fill="x", pady=2, padx=5)
        dots = ctk.CTkButton(row, text="...", width=28, height=28, corner_radius=6,
                             fg_color="transparent", hover_color=PALETTE["bg_hover"],
                             font=_font(size=14), text_color=PALETTE["text_mid"],
                             command=lambda sid=session_id, t=title, b=row: self._show_chat_menu(sid, t, b))
        dots.pack(side="right", padx=(0, 4))
        shown = (title or "").replace("\n", " ")
        if len(shown) > 26: shown = shown[:25] + "…"
        btn = ctk.CTkButton(row, text=shown, fg_color="transparent", hover_color=PALETTE["bg_hover"],
                            anchor="w", font=_font(size=13), text_color=PALETTE["text_hi"],
                            height=40, corner_radius=18, command=lambda sid=session_id: self.load_session(sid))
        btn.pack(side="left", fill="x", expand=True, padx=4, pady=2)
        if not is_active:
            dots.configure(text_color=PALETTE["bg_sidebar_2"])
            row.bind("<Enter>", lambda _e: dots.configure(text_color=PALETTE["text_mid"]))
            row.bind("<Leave>", lambda _e: dots.configure(text_color=PALETTE["bg_sidebar_2"]))

    def _show_chat_menu(self, session_id, title, widget):
        menu = tk.Menu(self, tearoff=0, bg=_tk_color(PALETTE["bg_sidebar_2"]), fg=_tk_color(PALETTE["text_hi"]),
                       activebackground=_tk_color(PALETTE["bg_hover"]), activeforeground=_tk_color(PALETTE["text_hi"]),
                       bd=0, relief="flat")
        menu.add_command(label="✏️  Rename",
                         command=lambda: EditChatDialog(self, title,
                                                       lambda n: self.rename_session(session_id, n)))
        menu.add_command(label="🗑️  Delete", foreground=_tk_color(PALETTE["danger"]),
                         command=lambda: self.delete_session(session_id))
        try:
            x = widget.winfo_rootx() + widget.winfo_width() - 110
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _drop_session_if_empty(self, session_id):
        if session_id is None: return
        with self._db_lock:
            self.cursor.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                self.conn.commit()

    def load_session(self, session_id):
        if self._is_responding: return
        if session_id != self.current_session_id:
            self._drop_session_if_empty(self.current_session_id)
        self.current_session_id = session_id
        with self._db_lock:
            self.cursor.execute(
                "SELECT sender, message, model FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,))
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
        self._scroll_to_bottom(force=True)

    def rename_session(self, session_id, new_title):
        with self._db_lock:
            self.cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
            self.conn.commit()
        if session_id == self.current_session_id:
            self._top_title.configure(text=new_title)
        self.load_sessions_list()

    def delete_session(self, session_id):
        if self._is_responding: return
        if not messagebox.askyesno("Delete", "Are you sure you want to delete this chat?", parent=self):
            return
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
        self._scroll_to_bottom(force=True)
        return bubble

    def send_message(self):
        if self._is_responding: return
        if getattr(self.prompt_entry, "_placeholder_active", False):
            return
        prompt = self.prompt_entry.get("1.0", "end-1c").strip()
        if not prompt: return
        if not self._prompt_history or self._prompt_history[-1] != prompt:
            self._prompt_history.append(prompt)
        self._prompt_history = self._prompt_history[-50:]
        model = self.chat_model_selector.get()
        self.prompt_entry.delete("1.0", "end")
        try: self.prompt_entry.edit_reset()
        except Exception: pass
        self.prompt_entry.configure(height=32)
        self.chat_input_frame.configure(height=60)
        self.prompt_entry._placeholder_active = False
        welcome_placeholder = getattr(self.welcome_entry, "_placeholder_text", "Ask Project-Kizen")
        self.welcome_entry.delete("1.0", "end")
        try: self.welcome_entry.edit_reset()
        except Exception: pass
        self.welcome_entry.insert("1.0", welcome_placeholder)
        self.welcome_entry.configure(height=32, text_color=PALETTE["text_lo"])
        self.welcome_input_frame.configure(height=60)
        self.welcome_entry._placeholder_active = True
        self.prompt_entry.focus_set()
        self.prompt_entry.mark_set("insert", "end")
        self._set_welcome_visible(False)
        self._add_bubble(sender=self.profile_name, text=prompt, is_user=True)
        self.save_message_to_db(self.profile_name, prompt)
        self._auto_title(prompt)
        ai_bubble = self._add_bubble(sender=model, text="▌ Thinking...", model=model, is_user=False)
        self._current_bubble = ai_bubble
        session_id = self.current_session_id
        self._stop_event.clear()
        self._is_responding = True
        self.send_btn.configure(text="■", fg_color=PALETTE["danger"], hover_color="#C03030",
                                command=self.stop_response)
        self._worker = threading.Thread(target=self._fetch_response, args=(model, session_id), daemon=True)
        self._worker.start()

    def _auto_title(self, prompt):
        with self._db_lock:
            self.cursor.execute("SELECT title FROM sessions WHERE id = ?", (self.current_session_id,))
            row = self.cursor.fetchone()
        if row and row[0] == "New Chat":
            title = prompt.replace("\n", " ")
            title = title[:40] + ("…" if len(title) > 40 else "")
            self.rename_session(self.current_session_id, title)

    def stop_response(self):
        if self._is_responding: self._stop_event.set()

    def _append_chunk(self, text):
        # OPT: use reset() instead of manual child destruction
        if self._current_bubble:
            if self._current_bubble._raw_text == "▌ Thinking...":
                self._current_bubble.reset()
            self._current_bubble.append_text(text)
            self._scroll_to_bottom()

    def _fetch_response(self, model, session_id):
        response_text = ""
        buffer = ""
        last_flush = time.monotonic()
        stopped = False
        try:
            for chunk in self._stream_response(model, session_id):
                if self._stop_event.is_set():
                    stopped = True
                    break
                response_text += chunk
                buffer += chunk
                now = time.monotonic()
                if now - last_flush >= FLUSH_INTERVAL:
                    self._post_ui(self._append_chunk, buffer)
                    buffer = ""
                    last_flush = now
            if buffer: self._post_ui(self._append_chunk, buffer)
            if self._stop_event.is_set():
                stopped = True
        except Exception as e:
            err = f"\n\n⚠️ Error: {e}"
            response_text += err
            self._post_ui(self._append_chunk, err)
            traceback.print_exc()
        finally:
            if stopped:
                response_text += " [stopped]"
                self._post_ui(self._append_chunk, " [stopped]")
            if response_text:
                try: self.save_message_to_db("AI", response_text, model, session_id)
                except Exception: traceback.print_exc()
            self._post_ui(self._on_response_finished)

    def _on_response_finished(self):
        try:
            if self._current_bubble:
                if self._current_bubble._raw_text == "▌ Thinking...":
                    self._current_bubble._raw_text = "No response received."
                self._current_bubble.finalize()
        except Exception:
            traceback.print_exc()
        finally:
            self._current_bubble = None
            self._is_responding = False
            self.send_btn.configure(text="↑", fg_color=PALETTE["accent"],
                                    hover_color=PALETTE["accent_dark"], text_color="#000000",
                                    command=self.send_message)
        try: grab = self.grab_current()
        except Exception: grab = None
        if grab is None or grab is self:
            self.prompt_entry.focus_set()
        self._scroll_to_bottom(force=True)

    def _build_gen_config(self):
        kw = {}
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if self.max_tokens and self.max_tokens > 0:
            kw["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            kw["top_p"] = self.top_p
        return kw

    def _stream_gemini(self, model, history):
        if not self.GEMINI_API_KEY or self.GEMINI_API_KEY.startswith("ENTER_"):
            raise RuntimeError("Missing Gemini API key.")
        contents = [{"role": "user" if m["role"] == "user" else "model",
                     "parts": [{"text": m["content"]}]} for m in history]
        client = genai.Client(api_key=self.GEMINI_API_KEY)

        cfg_kwargs = {}
        if self.temperature is not None:
            cfg_kwargs["temperature"] = self.temperature
        if self.max_tokens and self.max_tokens > 0:
            cfg_kwargs["max_output_tokens"] = self.max_tokens
        if self.top_p is not None:
            cfg_kwargs["top_p"] = self.top_p
        if self.system_prompt:
            cfg_kwargs["system_instruction"] = self.system_prompt

        try:
            config = genai.types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None
        except TypeError as e:
            if "system_instruction" in str(e).lower():
                cfg_kwargs.pop("system_instruction", None)
                config = genai.types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None
            else:
                raise

        kwargs = {"model": GEMINI_MODEL_MAP[model], "contents": contents}
        if config is not None:
            kwargs["config"] = config

        # OPT: close the underlying stream on stop so the HTTP connection is released.
        gen = client.models.generate_content_stream(**kwargs)
        try:
            for chunk in gen:
                if self._stop_event.is_set(): break
                if getattr(chunk, "text", None): yield chunk.text
        finally:
            close_fn = getattr(gen, "close", None)
            if close_fn:
                try: close_fn()
                except Exception: pass

    def _stream_openai_compatible(self, api_key, base_url, model_id, history):
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        messages = history
        if self.system_prompt:
            messages = [{"role": "system", "content": self.system_prompt}] + messages
        kwargs = {"model": model_id, "messages": messages, "stream": True}
        kwargs.update(self._build_gen_config())
        stream = client.chat.completions.create(**kwargs)
        try:
            for chunk in stream:
                if self._stop_event.is_set(): break
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        finally:
            try: stream.close()
            except Exception: pass

    def _stream_response(self, model, session_id):
        history = self._get_chat_history(session_id)
        if not history: raise RuntimeError("History is empty.")

        if model in GEMINI_MODEL_MAP:
            yield from self._stream_gemini(model, history)
            return

        providers = [
            (OPENAI_MODEL_MAP,     self.OPENAI_API_KEY,     None,                              "OpenAI"),
            (OPENROUTER_MODEL_MAP, self.OPENROUTER_API_KEY, "https://openrouter.ai/api/v1",     "OpenRouter"),
            (GROQ_MODEL_MAP,       self.GROQ_API_KEY,       "https://api.groq.com/openai/v1",  "Groq"),
        ]
        for model_map, api_key, base_url, provider_name in providers:
            if model in model_map:
                if not api_key or api_key.startswith("ENTER_"):
                    raise RuntimeError(f"Missing {provider_name} API key.")
                yield from self._stream_openai_compatible(api_key, base_url, model_map[model], history)
                return

        cm = next((c for c in self.custom_models if c["name"] == model), None)
        if cm:
            yield from self._stream_openai_compatible(
                cm.get("api_key") or "no-key", cm["base_url"], cm["model_id"], history)
            return

        raise ValueError(f"Unknown model: {model}")

    def save_message_to_db(self, sender, message, model=None, session_id=None):
        sid = session_id or self.current_session_id
        if not sid: return
        with self._db_lock:
            self.cursor.execute(
                "INSERT INTO messages (session_id, sender, message, model) VALUES (?, ?, ?, ?)",
                (sid, sender, message, model))
            self.conn.commit()

    def _get_chat_history(self, session_id):
        limit = max(1, int(self.history_limit or HISTORY_LIMIT))
        with self._db_lock:
            self.cursor.execute(
                "SELECT sender, message FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit))
            rows = self.cursor.fetchall()[::-1]
        history = []
        for s, m in rows:
            if s == "AI":
                m = re.sub(r"\n\n⚠️ Error: [\s\S]*$", "", m or "")
                m = re.sub(r" \[stopped\]$", "", m).strip()
                if not m:
                    m = "(no response)"
            history.append({"role": "assistant" if s == "AI" else "user", "content": m})
        while len(history) > 1 and history[0]["role"] == "assistant":
            history.pop(0)
        return history

    def open_profile_dialog(self): ProfileDialog(self, self.profile_name, self.update_profile_name)
    def open_settings_dialog(self):
        dlg = getattr(self, "_settings_dialog", None)
        if dlg is not None and dlg.winfo_exists():
            dlg.deiconify(); dlg.lift(); dlg.focus_force()
            return
        self._settings_dialog = SettingsDialog(self, self)

    def update_profile_name(self, new_name):
        if new_name.strip().upper() == "AI":
            self._toast.show("✗ 'AI' is a reserved name")
            return
        self.profile_name = new_name
        self.profile_btn.configure(text=f"👤  {self.profile_name}")
        self.save_config()

    def _on_close(self):
        if self.confirm_on_close:
            if not messagebox.askyesno("Exit", "Are you sure you want to exit?", parent=self):
                return
        self._stop_event.set()
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=3)
            if self._worker.is_alive():
                self._worker.join(timeout=2)
        if not self.save_config():
            try:
                messagebox.showwarning(
                    "Config not saved",
                    "Ayarlar dosyası yazılamadı.\n"
                    "Değişiklikler yalnızca bu oturum için geçerli olacak.",
                    parent=self,
                )
            except Exception:
                traceback.print_exc()
        # OPT: only close DB if worker is done; otherwise OS cleans up at process exit.
        worker_alive = self._worker is not None and self._worker.is_alive()
        if not worker_alive:
            try:
                self.conn.close()
            except Exception:
                traceback.print_exc()
        self.destroy()

    def _init_database(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        with self._db_lock:
            self.cursor.execute(
                "CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT)")
            self.cursor.execute(
                "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, sender TEXT, message TEXT, model TEXT, FOREIGN KEY(session_id) REFERENCES sessions(id))")
            self.cursor.execute(
                "DELETE FROM sessions WHERE id NOT IN (SELECT DISTINCT session_id FROM messages WHERE session_id IS NOT NULL)")
            self.conn.commit()

    def _post_ui(self, callback, *args):
        self._ui_queue.put((callback, args))

    def _poll_ui_queue(self):
        try:
            while True:
                callback, args = self._ui_queue.get_nowait()
                try: callback(*args)
                except Exception: traceback.print_exc()
        except queue.Empty:
            pass
        try:
            if self.winfo_exists():
                self.after(30, self._poll_ui_queue)
        except tk.TclError:
            pass

    def _scroll_to_bottom(self, force=False):
        if not force and not self.auto_scroll:
            return
        try:
            self.chat_scroll.update_idletasks()
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _on_enter_key(self, event):
        return self._on_textbox_key(event, self.prompt_entry, self.send_message)

    def _make_text_input(self, parent, placeholder):
        tb = ctk.CTkTextbox(parent, height=32, corner_radius=10,
                            border_width=0, fg_color="transparent",
                            text_color=PALETTE["text_hi"],
                            font=_font(size=15), wrap="word",
                            activate_scrollbars=False)
        tb._placeholder_text = placeholder
        tb._placeholder_active = True
        tb.insert("1.0", placeholder)
        tb.configure(text_color=PALETTE["text_lo"])

        def _on_focus_in(_e):
            if tb._placeholder_active:
                tb.delete("1.0", "end")
                tb.configure(text_color=PALETTE["text_hi"])
                tb._placeholder_active = False

        def _on_focus_out(_e):
            if not tb.get("1.0", "end-1c").strip():
                tb.delete("1.0", "end")
                tb.insert("1.0", placeholder)
                tb.configure(text_color=PALETTE["text_lo"])
                tb._placeholder_active = True
                self._autogrow_textbox(tb, 32, 152)

        def _on_up(_e):
            empty = tb._placeholder_active or not tb.get("1.0", "end-1c").strip()
            if empty and self._prompt_history:
                last = self._prompt_history[-1]
                tb.delete("1.0", "end")
                tb.configure(text_color=PALETTE["text_hi"])
                tb._placeholder_active = False
                tb.insert("1.0", last)
                tb.mark_set("insert", "end")
                self._autogrow_textbox(tb, 32, 152)
                return "break"

        tb.bind("<FocusIn>", _on_focus_in)
        tb.bind("<FocusOut>", _on_focus_out)
        tb.bind("<KeyRelease>", lambda _e: self._autogrow_textbox(tb, 32, 152))
        tb.bind("<Up>", _on_up)
        return tb

    def _autogrow_textbox(self, tb, min_px, max_px):
        if not isinstance(tb, ctk.CTkTextbox):
            return
        if getattr(tb, "_placeholder_active", False):
            n = 1
        else:
            try:
                tb.update_idletasks()
                n = int(tb._textbox.count("1.0", "end", "displaylines")[0])
            except Exception:
                n = tb.get("1.0", "end-1c").count("\n") + 1
            n = max(1, n)
        new_h = min(max_px, min_px + (n - 1) * 24)
        if new_h < min_px:
            new_h = min_px
        if int(tb.cget("height")) == new_h:
            return
        tb.configure(height=new_h)
        parent = tb.master
        parent.configure(height=new_h + 28)

    def _on_textbox_key(self, event, tb, send_fn):
        if event.keysym == "Return" and (event.state & 0x1):
            return None
        if not self.enter_sends:
            return None
        try:
            send_fn()
        except Exception:
            traceback.print_exc()
            return "break"
        if tb.winfo_ismapped():
            tb.focus_set()
            tb.mark_set("insert", "end")
        return "break"

    def _show_prompt_history(self, anchor_widget=None, target=None):
        if anchor_widget is None:
            anchor_widget = self.plus_btn
        if target is None:
            target = self.prompt_entry
        menu = tk.Menu(self, tearoff=0,
                       bg=_tk_color(PALETTE["bg_sidebar_2"]),
                       fg=_tk_color(PALETTE["text_hi"]),
                       activebackground=_tk_color(PALETTE["bg_hover"]),
                       activeforeground=_tk_color(PALETTE["text_hi"]),
                       bd=0, relief="flat")
        items = self._prompt_history[-20:]
        if not items:
            menu.add_command(label="(no history)", state="disabled")
        else:
            for p in reversed(items):
                label = p.replace("\n", " ")
                label = label[:60] + ("…" if len(label) > 60 else "")
                menu.add_command(label=label, command=lambda t=p: self._insert_prompt(t, target))
        try:
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
            menu.tk_popup(x, y)
        finally:
            try: menu.grab_release()
            except Exception: pass

    def _insert_prompt(self, text, tb=None):
        if tb is None:
            tb = self.prompt_entry
        tb.delete("1.0", "end")
        tb.configure(text_color=PALETTE["text_hi"])
        tb._placeholder_active = False
        tb.insert("1.0", text)
        tb.focus_set()
        tb.mark_set("insert", "end")
        self._autogrow_textbox(tb, 32, 152)

    def _bind_shortcuts(self):
        self.bind("<Control-n>", lambda e: self.create_new_chat())
        self.bind("<Control-N>", lambda e: self.create_new_chat())
        self.bind("<Control-comma>", lambda e: self.open_settings_dialog())
        self.bind("<Escape>", lambda e: self.stop_response() if self._is_responding else None)

if __name__ == "__main__":
    app = ProjectKizenClient()
    app.mainloop()