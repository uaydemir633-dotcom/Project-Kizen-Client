#!/usr/bin/env python3
"""
Project-Kizen — PySide6 migration (v1.3.0b1 - BETA).

This is a beta release migrating the UI from CustomTkinter to PySide6.
Please report any UI glitches, DPI scaling issues, or threading bugs.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sqlite3
import sys
import threading
import time
import traceback
from datetime import datetime

from PySide6.QtCore import (
    Qt, QTimer, Signal, Slot, QEvent, QObject,
)
from PySide6.QtGui import (
    QFont, QPalette, QTextCursor, QKeySequence, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QSlider,
    QScrollArea, QTabWidget, QCheckBox, QDialog, QMessageBox, QFileDialog,
    QMenu, QSizePolicy, QButtonGroup, QStackedWidget,
)

from google import genai
from openai import OpenAI


# ============================================================
# THEME / PALETTE
# ============================================================
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

_light_mode = False


def pal(key: str):
    """Resolve a palette entry for the current theme."""
    v = PALETTE[key]
    if isinstance(v, (tuple, list)):
        return v[0] if _light_mode else v[1]
    return v


def set_mode(mode: str):
    global _light_mode
    if mode == "light":
        _light_mode = True
    elif mode == "dark":
        _light_mode = False
    else:  # system
        try:
            hints = QApplication.styleHints()
            scheme = hints.colorScheme()
            _light_mode = (scheme == Qt.ColorScheme.Light)
        except Exception:
            app = QApplication.instance()
            if app:
                bg = app.palette().color(QPalette.Window)
                _light_mode = bg.lightness() > 128


def _darken(hex_color: str, factor: float = 0.85) -> str:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return "#" + hex_color
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#" + hex_color
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


_FONT_CACHE: dict = {}


def _font(size: int = 12, bold: bool = False, family: str | None = None, italic: bool = False) -> QFont:
    key = (size, bool(bold), family, bool(italic))
    f = _FONT_CACHE.get(key)
    if f is not None:
        return f
    f = QFont()
    if family:
        f.setFamily(family)
    f.setPointSize(size)
    f.setBold(bold)
    f.setItalic(italic)
    _FONT_CACHE[key] = f
    return f


_MONO_FONT = {
    "Windows": "Consolas",
    "Darwin":  "Menlo",
}.get(platform.system(), "DejaVu Sans Mono")


def build_qss() -> str:
    """Build the global QSS for the current theme/accent."""
    bg_app = pal("bg_app"); bg_sidebar = pal("bg_sidebar"); bg_sidebar_2 = pal("bg_sidebar_2")
    bg_input = pal("bg_input"); bg_hover = pal("bg_hover"); bg_code = pal("bg_code")
    text_hi = pal("text_hi"); text_mid = pal("text_mid"); text_lo = pal("text_lo")
    accent = pal("accent"); accent_dark = pal("accent_dark")
    danger = pal("danger"); success = pal("success"); border = pal("border")

    return f"""
    QMainWindow, QDialog {{ background-color: {bg_app}; }}
    QWidget {{ color: {text_hi}; }}
    QLabel {{ background: transparent; }}

    QFrame#Sidebar, QFrame#IconSidebar {{ background-color: {bg_sidebar}; }}
    QFrame#InputFrame {{ background-color: {bg_input}; border-radius: 30px; }}
    QFrame#UserBubble {{ background-color: {bg_sidebar_2}; border-radius: 18px; }}
    QFrame#CodeBlock {{ background-color: {bg_code}; border-radius: 8px; }}
    QFrame#SettingsCard {{ background-color: {bg_sidebar}; border-radius: 10px; }}

    QLabel#Avatar {{ background-color: {bg_hover}; border-radius: 16px; }}
    QLabel#AIAvatar {{ background-color: {bg_hover}; border-radius: 16px; color: {accent}; }}
    QLabel#SidebarHeader {{ color: {text_lo}; padding: 10px; font-weight: bold; }}

    QPushButton {{
        background-color: transparent; color: {text_hi};
        border: none; padding: 6px 12px; border-radius: 18px;
        text-align: left;
    }}
    QPushButton:hover {{ background-color: {bg_hover}; }}
    QPushButton#IconBtn {{ text-align: center; padding: 0; }}
    QPushButton#SendBtn {{
        background-color: {accent}; color: #000000;
        border-radius: 20px; font-weight: bold; text-align: center;
    }}
    QPushButton#SendBtn:hover {{ background-color: {accent_dark}; }}
    QPushButton#DangerBtn {{ color: {danger}; }}

    QTextEdit, QPlainTextEdit, QLineEdit {{
        background-color: {bg_input}; color: {text_hi};
        border: none; border-radius: 10px; padding: 6px 10px;
        selection-background-color: {accent}; selection-color: #000;
    }}
    QTextEdit:focus, QLineEdit:focus {{ background-color: {bg_input}; }}
    
    QTextEdit#TransparentInput {{
        background: transparent; border: none; padding: 4px;
    }}

    QComboBox {{
        background-color: {bg_input}; color: {text_hi}; border: none;
        border-radius: 18px; padding: 4px 12px;
    }}
    QComboBox:hover {{ background-color: {bg_hover}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background-color: {bg_sidebar_2}; color: {text_hi};
        selection-background-color: {bg_hover};
        border: 1px solid {border};
    }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {border}; min-height: 24px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: {text_lo}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{ height: 0; }}

    QMenu {{
        background-color: {bg_sidebar_2}; color: {text_hi};
        border: 1px solid {border}; padding: 4px;
    }}
    QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 4px; }}
    QMenu::item:selected {{ background-color: {bg_hover}; }}

    QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; top: -1px; }}
    QTabBar::tab {{
        background-color: {bg_sidebar}; color: {text_mid};
        padding: 6px 14px; border-radius: 8px; margin: 2px; border: none;
    }}
    QTabBar::tab:selected {{ background-color: {bg_sidebar_2}; color: {text_hi}; }}
    QTabBar::tab:hover {{ background-color: {bg_hover}; }}

    QSlider::groove:horizontal {{
        background: {bg_sidebar}; height: 4px; border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {accent}; width: 16px; height: 16px;
        margin: -6px 0; border-radius: 8px;
    }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}

    QCheckBox {{ color: {text_hi}; spacing: 8px; padding: 4px 0; }}
    QCheckBox::indicator {{
        width: 18px; height: 18px; border-radius: 4px;
        border: 1px solid {border}; background: {bg_input};
    }}
    QCheckBox::indicator:checked {{ background: {accent}; border: none; }}
    QCheckBox::indicator:hover {{ border: 1px solid {accent}; }}

    QToolTip {{
        background-color: #E3E3E3; color: #000;
        border: 1px solid #000; padding: 4px 8px;
    }}

    QLabel#Toast {{
        background-color: {bg_sidebar_2}; color: {text_hi};
        border-radius: 20px; padding: 10px 20px;
    }}
    QLabel#StatusSuccess {{ color: {success}; }}
    QLabel#StatusError   {{ color: {danger}; }}
    """


def _apply_theme(app: QApplication):
    app.setStyleSheet(build_qss())


# ============================================================
# CONSTANTS
# ============================================================
CONFIG_PATH = os.path.expanduser("~/.kizen_config.json")
HISTORY_LIMIT = 40
FLUSH_INTERVAL = 0.05
SESSION_LIMIT = 500

GEMINI_MODEL_MAP     = {"Gemini 2.5 Flash": "gemini-2.5-flash", "Gemini 2.5 Pro": "gemini-2.5-pro"}
OPENAI_MODEL_MAP     = {"GPT-4o-mini": "gpt-4o-mini", "GPT-4o": "gpt-4o"}
OPENROUTER_MODEL_MAP = {"OpenRouter Auto": "openrouter/auto", "OR Claude 3.5 Sonnet": "anthropic/claude-3.5-sonnet"}
GROQ_MODEL_MAP       = {"Groq Llama 3.3 70B": "llama-3.3-70b-versatile", "Groq Llama 3.1 8B": "llama-3.1-8b-instant"}

BASE_MODELS = (
    list(GEMINI_MODEL_MAP) + list(OPENAI_MODEL_MAP) +
    list(OPENROUTER_MODEL_MAP) + list(GROQ_MODEL_MAP)
)

_KIZEN_DIR = os.path.expanduser("~/.kizen")
DB_PATH = os.path.join(_KIZEN_DIR, "kizen_chats.db")
CHAT_STYLE = {"size": 14}

SYSTEM_PROMPT_PRESETS = {
    "— Select a preset —": None,
    "None (empty)": "",
    "Helpful Assistant": "You are a helpful, accurate and friendly assistant. Answer clearly and concisely.",
    "Senior Developer": ("You are a senior software engineer. Give production-quality code, explain trade-offs "
                         "briefly, point out bugs and edge cases, and prefer clear, idiomatic solutions."),
    "Turkish Assistant": "Always respond in Turkish. Give clear, concise, and accurate answers.",
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


def _clean_key(value: str | None) -> str:
    value = re.sub(r"[\s\u200b\u200c\u200d\u2060\ufeff]", "", value or "")
    value = value.strip("\"'")
    if value.startswith("ENTER_"):
        return ""
    return value


def _fit_window_size(w: int, h: int, margin_w: int = 40, margin_h: int = 90) -> tuple[int, int]:
    screen = QApplication.primaryScreen().availableGeometry()
    return max(200, min(w, screen.width() - margin_w)), max(150, min(h, screen.height() - margin_h))


def _center_dialog(dialog: QDialog, parent: QWidget | None, w: int, h: int):
    w, h = _fit_window_size(w, h)
    dialog.resize(w, h)
    if parent is not None:
        try:
            pg = parent.geometry()
            cx, cy = pg.center().x(), pg.center().y()
            dialog.move(cx - w // 2, cy - h // 2)
        except Exception:
            pass


# ============================================================
# WIDGETS
# ============================================================
class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignCenter)
        self.setFont(_font(13))
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show(self, text: str, duration: int = 1800):
        self.setText(text)
        self.adjustSize()
        p = self.parentWidget()
        if p:
            x = (p.width() - self.width()) // 2
            self.move(max(0, x), int(p.height() * 0.04))
        super().show()
        self.raise_()
        self._timer.start(duration)

    def show_message(self, text: str, duration: int = 1800):
        self.show(text, duration)


class MessageBubble(QWidget):
    """A chat message row — user (right-aligned bubble) or AI (left-aligned flat)."""

    def __init__(self, parent: QWidget, sender: str, text: str, model: str | None = None,
                 is_user: bool = False, chat_font_size: int = 14):
        super().__init__(parent)
        self.sender = sender
        self.model = model
        self.is_user = is_user
        self._raw_text = text
        self._labels: list[QLabel] = []
        self._last_label_text = ""
        self._finalized = False
        self._chat_font_size = chat_font_size
        self._build()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 8, 20, 8)
        outer.setSpacing(10)

        avatar = QLabel("👤" if self.is_user else "⚡")
        avatar.setObjectName("Avatar" if self.is_user else "AIAvatar")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFont(_font(14, bold=not self.is_user))

        bubble = QFrame()
        bubble.setObjectName("UserBubble" if self.is_user else "AIBubble")
        bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        content = QVBoxLayout(bubble)
        content.setContentsMargins(16, 10, 16, 12)
        content.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(self.sender if self.is_user else (self.model or "AI"))
        name_lbl.setFont(_font(13, bold=True))
        header.addWidget(name_lbl)
        header.addStretch(1)
        if not self.is_user:
            copy_btn = QPushButton("📋")
            copy_btn.setObjectName("IconBtn")
            copy_btn.setFixedSize(26, 26)
            copy_btn.setFont(_font(11))
            copy_btn.setToolTip("Copy response")
            copy_btn.clicked.connect(self._copy)
            header.addWidget(copy_btn)
        content.addLayout(header)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(4)
        self.body_layout.setAlignment(Qt.AlignTop)
        content.addWidget(self.body)

        if self.is_user:
            outer.addStretch(1)
            outer.addWidget(bubble, 0)
            outer.addWidget(avatar, 0, Qt.AlignTop)
            bubble.setMaximumWidth(680)
        else:
            outer.addWidget(avatar, 0, Qt.AlignTop)
            outer.addWidget(bubble, 1)

        if self.is_user:
            self._render_user(self._raw_text)
        else:
            if self._raw_text:
                self._render_text(self._raw_text)

    def _render_user(self, text: str):
        lbl = QLabel(text)
        lbl.setFont(_font(self._chat_font_size))
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body_layout.addWidget(lbl)
        self._labels.append(lbl)
        self._last_label_text = text

    def _render_text(self, text: str):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._labels.clear()
        self._last_label_text = ""

        parts = re.split(r"(```[^\n`]*(?:\n[\s\S]*?)?```)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("```"):
                nl = part.find("\n")
                code = part[nl + 1:] if nl >= 0 else part[3:]
                if code.endswith("```"):
                    code = code[:-3]
                code = code.rstrip("\n")
                self._add_code_block(code)
                self._last_label_text = code
            else:
                self._add_text_label(part)
                self._last_label_text = part

    def _add_text_label(self, text: str):
        lbl = QLabel(text)
        lbl.setFont(_font(self._chat_font_size))
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body_layout.addWidget(lbl)
        self._labels.append(lbl)

    def _add_code_block(self, code: str):
        frame = QFrame()
        frame.setObjectName("CodeBlock")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(code)
        f = QFont(_MONO_FONT)
        f.setPointSize(max(9, self._chat_font_size - 1))
        lbl.setFont(f)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        fl.addWidget(lbl)
        self.body_layout.addWidget(frame)
        self._labels.append(lbl)

    def append_text(self, text: str):
        self._raw_text += text
        if self._finalized:
            self._render_text(self._raw_text)
            return
        if not self._labels:
            self._add_text_label(text)
            self._last_label_text = text
        else:
            self._last_label_text += text
            self._labels[-1].setText(self._last_label_text)

    def reset(self):
        self._raw_text = ""
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._labels.clear()
        self._last_label_text = ""

    def finalize(self):
        if self._finalized:
            return
        self._finalized = True
        self._render_text(self._raw_text)

    def _copy(self):
        try:
            QApplication.clipboard().setText(self._raw_text)
            win = self.window()
            if hasattr(win, "_toast"):
                win._toast.show("✓ Copied")
        except Exception:
            pass


# ============================================================
# DIALOGS
# ============================================================
class TextInputDialog(QDialog):
    TITLE = ""
    HEADER = ""
    PLACEHOLDER = ""
    SAVE_LABEL = "Save"
    SIZE = (380, 200)

    def __init__(self, parent: QWidget | None, current_value: str, callback):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.setModal(True)
        _center_dialog(self, parent, *self.SIZE)
        self.callback = callback

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(12)

        lbl = QLabel(self.HEADER)
        lbl.setFont(_font(16, bold=True))
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)

        self.entry = QLineEdit(current_value)
        self.entry.setPlaceholderText(self.PLACEHOLDER)
        self.entry.setFixedHeight(38)
        self.entry.returnPressed.connect(self._save)
        v.addWidget(self.entry)

        btn = QPushButton(self.SAVE_LABEL)
        btn.setFixedHeight(40)
        btn.setStyleSheet(
            f"background-color: {pal('accent')}; color: #000; "
            f"border-radius: 20px; font-weight: bold; text-align: center;"
        )
        btn.clicked.connect(self._save)
        v.addWidget(btn)

        self.entry.setFocus()
        self.entry.selectAll()

    def _save(self):
        val = self.entry.text().strip()
        try:
            if val:
                self.callback(val)
        finally:
            self.accept()


class ProfileDialog(TextInputDialog):
    TITLE = "Profile"
    HEADER = "Profile Name"
    PLACEHOLDER = "Enter your name"


class EditChatDialog(TextInputDialog):
    TITLE = "Rename Chat"
    HEADER = "New Title"
    PLACEHOLDER = "Enter title"


class CustomModelDialog(QDialog):
    def __init__(self, parent: QWidget | None, callback, existing: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Custom Model" if existing else "Add Custom Model")
        self.setModal(True)
        _center_dialog(self, parent, 480, 540)
        self.setMinimumSize(400, 400)
        self.callback = callback
        self.existing = existing or {}

        QShortcut(QKeySequence("Escape"), self, self.reject)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(8)

        title = QLabel("Custom Model")
        title.setFont(_font(20, bold=True))
        v.addWidget(title)

        hint = QLabel("Any OpenAI-compatible endpoint (Ollama, LM Studio, LiteLLM, vLLM, ...)")
        hint.setFont(_font(11))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {pal('text_lo')};")
        v.addWidget(hint)

        v.addSpacing(6)
        self.name_edit = self._add_field(v, "Display Name", "name", "My Local Llama")
        self.url_edit  = self._add_field(v, "Base URL", "base_url", "http://localhost:11434/v1")
        self.key_edit  = self._add_field(v, "API Key (optional)", "api_key",
                                         "Optional (leave empty for local servers)", password=True)
        self.id_edit   = self._add_field(v, "Model ID", "model_id", "llama3.2")
        self.id_edit.returnPressed.connect(self._save)

        v.addStretch(1)
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet(
            f"background-color: {pal('bg_sidebar')}; border-radius: 20px; text-align: center;"
        )
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(40)
        save_btn.setStyleSheet(
            f"background-color: {pal('accent')}; color: #000; "
            f"border-radius: 20px; font-weight: bold; text-align: center;"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        v.addLayout(btn_row)

    def _add_field(self, layout: QVBoxLayout, label: str, key: str, placeholder: str,
                   password: bool = False) -> QLineEdit:
        lbl = QLabel(label)
        lbl.setFont(_font(12, bold=True))
        layout.addWidget(lbl)

        row = QHBoxLayout()
        row.setSpacing(6)
        edit = QLineEdit(self.existing.get(key, ""))
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(38)
        if password:
            edit.setEchoMode(QLineEdit.Password)
        row.addWidget(edit, 1)

        if password:
            toggle = QPushButton("👁")
            toggle.setObjectName("IconBtn")
            toggle.setFixedSize(38, 38)
            state = {"hidden": True}

            def _tog():
                state["hidden"] = not state["hidden"]
                edit.setEchoMode(QLineEdit.Password if state["hidden"] else QLineEdit.Normal)
                toggle.setText("👁" if state["hidden"] else "🙈")

            toggle.clicked.connect(_tog)
            row.addWidget(toggle)

        layout.addLayout(row)
        return edit

    def _save(self):
        data = {
            "name":     self.name_edit.text().strip(),
            "base_url": self.url_edit.text().strip().rstrip("/"),
            "api_key":  _clean_key(self.key_edit.text()),
            "model_id": self.id_edit.text().strip(),
        }
        if not (data["name"] and data["base_url"] and data["model_id"]):
            QMessageBox.warning(self, "Missing Fields",
                                "Display Name, Base URL and Model ID are required.")
            return
        if not re.match(r"^https?://\S+$", data["base_url"], re.IGNORECASE):
            QMessageBox.warning(self, "Invalid URL",
                                "Base URL must start with http:// or https://")
            return
        if self.callback(data) is False:
            return
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None, app: ProjectKizenClient):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Settings")
        self.setModal(True)
        _center_dialog(self, parent, 640, 800)
        self.setMinimumSize(560, 560)

        self.working_custom_models = [dict(c) for c in app.custom_models]
        self._initial_mode = app.appearance_mode
        self._custom_dialog: CustomModelDialog | None = None
        self._testing = False
        self._initial_snapshot = None

        QShortcut(QKeySequence("Escape"), self, self._on_cancel)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)

        title = QLabel("Settings")
        title.setFont(_font(22, bold=True))
        v.addWidget(title)

        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)

        self._build_general_tab()
        self._build_chat_tab()
        self._build_appearance_tab()
        self._build_api_tab()
        self._build_data_tab()
        self._build_about_tab()

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setFont(_font(12))
        v.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        test_btn = QPushButton("Test")
        test_btn.setFixedHeight(40)
        test_btn.setStyleSheet(
            f"background-color: {pal('bg_sidebar')}; border-radius: 20px; padding: 0 20px; text-align: center;"
        )
        test_btn.clicked.connect(self._test_connection)
        self.test_btn = test_btn

        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(40)
        save_btn.setStyleSheet(
            f"background-color: {pal('accent')}; color: #000; "
            f"border-radius: 20px; font-weight: bold; padding: 0 20px; text-align: center;"
        )
        save_btn.clicked.connect(self._save)

        btn_row.addWidget(test_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(save_btn)
        v.addLayout(btn_row)

        QTimer.singleShot(0, lambda: setattr(self, "_initial_snapshot", self._snapshot()))

    def _snapshot(self):
        return (
            self.profile_edit.text(),
            self.default_model_combo.currentText(),
            self.enter_sends_cb.isChecked(),
            self.auto_scroll_cb.isChecked(),
            self.confirm_close_cb.isChecked(),
            self.system_prompt_edit.toPlainText().strip(),
            round(self.temp_slider.value() / 20.0, 2),
            round(self.top_p_slider.value() / 20.0, 2),
            self.max_tokens_edit.text(),
            self.history_edit.text(),
            self.theme_group.checkedButton().text() if self.theme_group.checkedButton() else "Dark",
            self.accent_color,
            self.font_slider.value(),
            self.openai_edit.text(),
            self.gemini_edit.text(),
            self.openrouter_edit.text(),
            self.groq_edit.text(),
            json.dumps(self.working_custom_models, sort_keys=True),
        )

    def _on_cancel(self):
        try:
            changed = (self._snapshot() != self._initial_snapshot)
        except Exception:
            changed = False
        if changed:
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "You have unsaved changes. Save them before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self._save()
                return
        try:
            set_mode(self._initial_mode)
            _apply_theme(QApplication.instance())
        except Exception:
            pass
        self.reject()

    def reject(self):
        if getattr(self.app, "_settings_dialog", None) is self:
            self.app._settings_dialog = None
        super().reject()

    def closeEvent(self, event):
        self._on_cancel()
        event.ignore()

    # ---------- tabs ----------
    def _build_general_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)

        v.addWidget(self._section_title("Profile"))
        v.addWidget(self._label("Your Name"))
        self.profile_edit = QLineEdit(self.app.profile_name)
        self.profile_edit.setFixedHeight(38)
        v.addWidget(self.profile_edit)

        v.addWidget(self._section_title("Defaults"))
        v.addWidget(self._label("Default Model"))
        self.default_model_combo = QComboBox()
        self.default_model_combo.addItems(self.app._get_all_models())
        self.default_model_combo.setFixedHeight(38)
        if self.app.default_model in self.app._get_all_models():
            self.default_model_combo.setCurrentText(self.app.default_model)
        v.addWidget(self.default_model_combo)

        v.addWidget(self._section_title("Behavior"))
        self.enter_sends_cb = QCheckBox("Enter sends message (Ctrl+Enter always sends)")
        self.enter_sends_cb.setChecked(self.app.enter_sends)
        v.addWidget(self.enter_sends_cb)
        self.auto_scroll_cb = QCheckBox("Auto-scroll while streaming")
        self.auto_scroll_cb.setChecked(self.app.auto_scroll)
        v.addWidget(self.auto_scroll_cb)
        self.confirm_close_cb = QCheckBox("Confirm before closing")
        self.confirm_close_cb.setChecked(self.app.confirm_on_close)
        v.addWidget(self.confirm_close_cb)

        v.addStretch(1)
        self.tabs.addTab(scroll, "General")

    def _build_chat_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)

        v.addWidget(self._section_title("System Prompt"))
        hint = QLabel("Injected as system message on every request. Empty = no system message.")
        hint.setFont(_font(11))
        hint.setStyleSheet(f"color: {pal('text_lo')};")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(SYSTEM_PROMPT_PRESETS.keys()))
        self.preset_combo.setFixedHeight(34)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        v.addWidget(self.preset_combo)

        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setFixedHeight(110)
        self.system_prompt_edit.setPlainText(self.app.system_prompt)
        self.system_prompt_edit.textChanged.connect(self._update_prompt_count)
        v.addWidget(self.system_prompt_edit)

        self.prompt_count_label = QLabel("")
        self.prompt_count_label.setFont(_font(10))
        self.prompt_count_label.setAlignment(Qt.AlignRight)
        self.prompt_count_label.setStyleSheet(f"color: {pal('text_lo')};")
        v.addWidget(self.prompt_count_label)
        self._update_prompt_count()

        v.addWidget(self._section_title("Parameters"))
        self.temp_slider, self.temp_value = self._add_slider(
            v, "Temperature", int(self.app.temperature * 20), 0, 40, fmt=lambda val: f"{val/20:.2f}"
        )
        self.top_p_slider, self.top_p_value = self._add_slider(
            v, "Top-P", int(self.app.top_p * 20), 0, 20, fmt=lambda val: f"{val/20:.2f}"
        )

        v.addWidget(self._label("Max Tokens", hint="0 = provider default"))
        self.max_tokens_edit = QLineEdit(str(self.app.max_tokens))
        self.max_tokens_edit.setFixedHeight(38)
        v.addWidget(self.max_tokens_edit)

        v.addWidget(self._label("History Limit", hint="Max messages sent as context."))
        self.history_edit = QLineEdit(str(self.app.history_limit))
        self.history_edit.setFixedHeight(38)
        v.addWidget(self.history_edit)

        v.addStretch(1)
        self.tabs.addTab(scroll, "Chat")

    def _build_appearance_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)

        v.addWidget(self._section_title("Theme Mode"))

        theme_row = QHBoxLayout()
        self.theme_group = QButtonGroup(self)
        cur_mode = self.app.appearance_mode.capitalize()
        for name in ("Dark", "Light", "System"):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setStyleSheet(
                f"QPushButton {{ background: {pal('bg_sidebar')}; "
                f"border-radius: 10px; padding: 4px 16px; text-align: center; }}"
                f"QPushButton:checked {{ background: {pal('bg_sidebar_2')}; font-weight: bold; }}"
            )
            self.theme_group.addButton(btn)
            theme_row.addWidget(btn)
            btn.clicked.connect(lambda _c=False, n=name: self._on_theme_change(n))
            if name == cur_mode:
                btn.setChecked(True)
        v.addLayout(theme_row)

        v.addWidget(self._section_title("Accent Color"))
        hint = QLabel("Theme previews instantly. Accent updates apply on save.")
        hint.setFont(_font(11))
        hint.setStyleSheet(f"color: {pal('text_lo')};")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.accent_color = self.app.accent_color
        acc_row = QHBoxLayout()
        self.accent_buttons = []
        for hex_color in ACCENT_PRESETS:
            btn = QPushButton()
            btn.setFixedSize(44, 44)
            self._style_accent_button(btn, hex_color, hex_color == self.accent_color)
            btn.clicked.connect(lambda _c=False, c=hex_color: self._select_accent(c))
            acc_row.addWidget(btn)
            self.accent_buttons.append((hex_color, btn))
        acc_row.addStretch(1)
        v.addLayout(acc_row)

        v.addWidget(self._section_title("Chat Text"))
        self.font_slider, self.font_value = self._add_slider(
            v, "Font Size", self.app.chat_font_size, 11, 20,
            fmt=lambda val: f"{val}", on_change=self._update_font_preview
        )
        self.font_preview = QLabel("Preview: The quick brown fox jumps over the lazy dog.")
        self.font_preview.setFont(_font(self.app.chat_font_size))
        self.font_preview.setStyleSheet(
            f"background-color: {pal('bg_sidebar')}; border-radius: 10px; padding: 10px;"
        )
        v.addWidget(self.font_preview)

        v.addStretch(1)
        self.tabs.addTab(scroll, "Appearance")

    def _build_api_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)

        v.addWidget(self._section_title("Provider API Keys"))

        self.openai_edit     = self._add_key_field(v, "OpenAI API Key",     self.app.OPENAI_API_KEY)
        self.gemini_edit     = self._add_key_field(v, "Gemini API Key",     self.app.GEMINI_API_KEY)
        self.openrouter_edit = self._add_key_field(v, "OpenRouter API Key", self.app.OPENROUTER_API_KEY)
        self.groq_edit       = self._add_key_field(v, "Groq API Key",       self.app.GROQ_API_KEY)

        v.addWidget(self._section_title("Custom Models"))
        hint = QLabel("Add any OpenAI-compatible endpoint as a selectable model.")
        hint.setFont(_font(11))
        hint.setStyleSheet(f"color: {pal('text_lo')};")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.custom_models_box = QVBoxLayout()
        v.addLayout(self.custom_models_box)
        self._render_custom_models()

        add_btn = QPushButton("＋ Add Custom Model")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(
            f"background-color: {pal('bg_sidebar')}; border-radius: 10px; padding: 4px 12px; text-align: center;"
        )
        add_btn.clicked.connect(self._add_custom_model)
        v.addWidget(add_btn)

        v.addStretch(1)
        self.tabs.addTab(scroll, "API Keys")

    def _build_data_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(6)

        v.addWidget(self._section_title("Storage"))
        self.stats_label = QLabel("")
        self.stats_label.setFont(_font(12))
        self.stats_label.setStyleSheet(
            f"background-color: {pal('bg_sidebar')}; border-radius: 10px; padding: 10px;"
        )
        self.stats_label.setWordWrap(True)
        v.addWidget(self.stats_label)
        self._refresh_stats()

        v.addWidget(self._section_title("Chats"))
        self._action_button(v, "⬇  Export all chats (JSON)", self._export_chats_json)
        self._action_button(v, "⬇  Export all chats (Markdown)", self._export_chats_md)
        self._action_button(v, "⬆  Import chats (JSON)", self._import_chats_json)
        self._action_button(v, "🗑  Delete all chats", self._delete_all_chats, danger=True)

        v.addWidget(self._section_title("Settings"))
        self.include_keys_cb = QCheckBox(
            "Include API keys when exporting settings (⚠ exported as plain text)")
        self.include_keys_cb.setChecked(False)
        v.addWidget(self.include_keys_cb)
        self._action_button(v, "⬇  Export settings", self._export_settings)
        self._action_button(v, "⬆  Import settings", self._import_settings)
        self._action_button(v, "↺  Reset to defaults (keeps API keys & custom models)",
                            self._reset_defaults, danger=True)

        v.addStretch(1)
        self.tabs.addTab(scroll, "Data")

    def _build_about_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(6)

        title = QLabel("Project-Kizen")
        title.setFont(_font(16, bold=True))
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)
        sub = QLabel("Multi-provider AI client.")
        sub.setFont(_font(12))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color: {pal('text_mid')};")
        v.addWidget(sub)

        lic_title = QLabel("MIT License")
        lic_title.setFont(_font(12, bold=True))
        v.addWidget(lic_title)

        box = QTextEdit()
        f = QFont(_MONO_FONT)
        f.setPointSize(11)
        box.setFont(f)
        box.setPlainText(LICENSE_TEXT)
        box.setReadOnly(True)
        v.addWidget(box, 1)

        self.tabs.addTab(w, "About")

    # ---------- helpers ----------
    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(_font(13, bold=True))
        return lbl

    def _label(self, text: str, hint: str | None = None) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 4, 0, 0)
        v.setSpacing(2)
        lbl = QLabel(text)
        lbl.setFont(_font(12, bold=True))
        v.addWidget(lbl)
        if hint:
            h = QLabel(hint)
            h.setFont(_font(10))
            h.setStyleSheet(f"color: {pal('text_lo')};")
            h.setWordWrap(True)
            v.addWidget(h)
        return w

    def _add_key_field(self, parent_layout: QVBoxLayout, label: str, value: str) -> QLineEdit:
        parent_layout.addWidget(self._label(label))
        row = QHBoxLayout()
        row.setSpacing(6)
        edit = QLineEdit(value)
        edit.setEchoMode(QLineEdit.Password)
        edit.setFixedHeight(38)
        row.addWidget(edit, 1)

        toggle = QPushButton("👁")
        toggle.setObjectName("IconBtn")
        toggle.setFixedSize(38, 38)
        state = {"hidden": True}

        def _tog():
            state["hidden"] = not state["hidden"]
            edit.setEchoMode(QLineEdit.Password if state["hidden"] else QLineEdit.Normal)
            toggle.setText("👁" if state["hidden"] else "🙈")

        toggle.clicked.connect(_tog)
        row.addWidget(toggle)
        parent_layout.addLayout(row)
        return edit

    def _action_button(self, parent_layout: QVBoxLayout, text: str, cmd, danger: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            f"background-color: {pal('bg_sidebar')}; border-radius: 10px; "
            f"padding: 4px 12px; text-align: left;"
            + (f" color: {pal('danger')};" if danger else "")
        )
        btn.clicked.connect(cmd)
        parent_layout.addWidget(btn)
        return btn

    def _add_slider(self, layout: QVBoxLayout, label: str, value: int, mn: int, mx: int,
                    fmt=lambda val: str(val), on_change=None):
        head = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFont(_font(12, bold=True))
        val_lbl = QLabel(fmt(value))
        val_lbl.setFont(_font(12))
        head.addWidget(lbl)
        head.addStretch(1)
        head.addWidget(val_lbl)
        layout.addLayout(head)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(mn, mx)
        slider.setValue(value)
        layout.addWidget(slider)

        def _changed(v):
            val_lbl.setText(fmt(v))
            if on_change:
                on_change(v)

        slider.valueChanged.connect(_changed)
        return slider, val_lbl

    def _style_accent_button(self, btn: QPushButton, hex_color: str, selected: bool):
        border = f"border: 3px solid {pal('text_hi')};" if selected else "border: 3px solid transparent;"
        btn.setStyleSheet(
            f"background-color: {hex_color}; border-radius: 22px; {border}"
        )

    def _select_accent(self, hex_color: str):
        self.accent_color = hex_color
        for c, btn in self.accent_buttons:
            self._style_accent_button(btn, c, c == hex_color)

    def _on_theme_change(self, mode_name: str):
        mode = mode_name.lower()
        set_mode(mode)
        _apply_theme(QApplication.instance())

    def _apply_preset(self, name: str):
        text = SYSTEM_PROMPT_PRESETS.get(name)
        if text is None:
            return
        current = self.system_prompt_edit.toPlainText().strip()
        if current and current != text:
            reply = QMessageBox.question(
                self, "Overwrite prompt",
                "Replace the current system prompt with this preset?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.preset_combo.setCurrentText("— Select a preset —")
                return
        self.system_prompt_edit.setPlainText(text or "")
        self._update_prompt_count()
        self.preset_combo.setCurrentText("— Select a preset —")

    def _update_prompt_count(self):
        text = self.system_prompt_edit.toPlainText().strip()
        self.prompt_count_label.setText(
            f"{len(text)} chars · ~{(len(text) + 3) // 4} tokens (estimate)")

    def _update_font_preview(self, v: int):
        self.font_preview.setFont(_font(int(v)))

    def _refresh_stats(self):
        app = self.app
        with app._db_lock:
            app.cursor.execute(
                "SELECT COUNT(*) FROM sessions WHERE id IN "
                "(SELECT DISTINCT session_id FROM messages)")
            n_sessions = app.cursor.fetchone()[0]
            app.cursor.execute("SELECT COUNT(*) FROM messages")
            n_messages = app.cursor.fetchone()[0]
        try:
            size_kb = os.path.getsize(DB_PATH) / 1024
        except OSError:
            size_kb = 0
        size_txt = f"{size_kb / 1024:.2f} MB" if size_kb > 1024 else f"{size_kb:.1f} KB"
        self.stats_label.setText(
            f"Chats: {n_sessions}    Messages: {n_messages}    Database: {size_txt}\n"
            f"Location: {os.path.abspath(DB_PATH)}"
        )

    def _collect_chats(self) -> list[dict]:
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

    def _ask_save(self, ext: str, title: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        path, _ = QFileDialog.getSaveFileName(
            self, title, f"kizen_{stamp}{ext}",
            f"{ext.upper().strip('.')} (*{ext});;All files (*)"
        )
        return path

    def _export_chats_json(self):
        path = self._ask_save(".json", "Export chats")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"app": "Project-Kizen", "version": 1, "sessions": self._collect_chats()},
                    f, ensure_ascii=False, indent=2)
            self._status(f"✓ Exported to {os.path.basename(path)}")
        except Exception as e:
            self._status(f"✗ Export failed: {e}", error=True)

    def _export_chats_md(self):
        path = self._ask_save(".md", "Export chats as Markdown")
        if not path:
            return
        try:
            lines = ["# Project-Kizen Chats", ""]
            for ses in self._collect_chats():
                lines += [f"## {ses['title']}", f"_{ses['created_at']}_", ""]
                for m in ses["messages"]:
                    who = (f"AI ({m['model']})" if m["model"] else "AI") if m["sender"] == "AI" else m["sender"]
                    lines += [f"**{who}:**", "", m["message"], ""]
                lines += ["---", ""]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._status(f"✓ Exported to {os.path.basename(path)}")
        except Exception as e:
            self._status(f"✗ Export failed: {e}", error=True)

    def _import_chats_json(self):
        if self.app._is_responding:
            self._status("✗ Wait until the current response finishes.", error=True)
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import chats", "", "JSON (*.json);;All files (*)")
        if not path:
            return
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
                        if not isinstance(ses, dict):
                            continue
                        msgs = [m for m in (ses.get("messages") or []) if isinstance(m, dict)]
                        if not msgs:
                            continue
                        title = str(ses.get("title") or "Imported Chat")
                        created = str(ses.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M"))
                        key = (title, created)
                        if len(msgs) in existing.get(key, set()):
                            skipped += 1
                            continue
                        app.cursor.execute(
                            "INSERT INTO sessions (title, created_at) VALUES (?, ?)",
                            (title, created))
                        sid = app.cursor.lastrowid
                        for m in msgs:
                            app.cursor.execute(
                                "INSERT INTO messages (session_id, sender, message, model) "
                                "VALUES (?, ?, ?, ?)",
                                (sid, str(m.get("sender") or "User"),
                                 str(m.get("message") or ""),
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
                if skipped:
                    msg += f", skipped {skipped} duplicate(s)"
                self._status(msg)
            else:
                self._status("No chats found in file.", error=True)
        except Exception as e:
            self._status(f"✗ Import failed: {e}", error=True)

    def _delete_all_chats(self):
        app = self.app
        if app._is_responding:
            self._status("✗ Wait until the current response finishes.", error=True)
            return
        reply = QMessageBox.question(
            self, "Delete all chats",
            "This permanently deletes ALL chats. Continue?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        with app._db_lock:
            app.cursor.execute("DELETE FROM messages")
            app.cursor.execute("DELETE FROM sessions")
            app.conn.commit()
        try:
            tmp = sqlite3.connect(DB_PATH, isolation_level=None)
            try:
                tmp.execute("VACUUM")
            finally:
                tmp.close()
        except Exception:
            pass
        app._create_new_chat_internal()
        self._refresh_stats()
        self._status("✓ All chats deleted")

    def _export_settings(self):
        path = self._ask_save(".json", "Export settings")
        if not path:
            return
        try:
            data = self.app._config_dict()
            if not self.include_keys_cb.isChecked():
                for k in ("openai_key", "gemini_key", "openrouter_key", "groq_key"):
                    data.pop(k, None)
                data["custom_models"] = [
                    {**c, "api_key": ""} for c in data.get("custom_models", [])]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._status(f"✓ Settings exported to {os.path.basename(path)}")
        except Exception as e:
            self._status(f"✗ Export failed: {e}", error=True)

    def _import_settings(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import settings", "", "JSON (*.json);;All files (*)")
        if not path:
            return
        reply = QMessageBox.question(
            self, "Import settings",
            "This will overwrite your current settings.\n"
            "API keys and custom models that are empty in the file will be preserved.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Invalid settings file.")
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
                        skipped.append(key)
                        continue
                    clean = self.app._sanitize_config({key: val})[key]
                    if not clean:
                        if val:
                            skipped.append(key)
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
            msg = "✓ Settings imported" + (
                f" (skipped invalid: {', '.join(skipped)})" if skipped else "")
            self._apply_and_reopen(cfg, msg)
        except Exception as e:
            self._status(f"✗ Import failed: {e}", error=True)

    @staticmethod
    def _accept_import_value(val, sanitized):
        if isinstance(sanitized, bool):
            return isinstance(val, bool) and val == sanitized
        if sanitized == val:
            return True
        try:
            if isinstance(sanitized, float) and float(val) == sanitized:
                return True
            if isinstance(sanitized, int) and not isinstance(sanitized, bool) and int(val) == sanitized:
                return True
        except (TypeError, ValueError):
            pass
        if isinstance(val, str) and isinstance(sanitized, str):
            return sanitized.lower() == val.strip().lower()
        return False

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, "Reset",
            "Reset all settings to defaults?\nAPI keys and custom models will be kept.",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        cfg = self.app._config_dict()
        cfg.update(DEFAULT_SETTINGS)
        self._apply_and_reopen(cfg, "✓ Settings reset")

    def _apply_and_reopen(self, cfg, msg):
        app = self.app
        old_default, old_font = app.default_model, app.chat_font_size
        app._apply_config_values(cfg)
        app.profile_btn.setText(f"👤  {app.profile_name}")
        app._refresh_model_selectors()
        if app.default_model != old_default and not app._is_responding:
            target = app.default_model if app.default_model in app._get_all_models() else BASE_MODELS[0]
            app.chat_model_selector.setCurrentText(target)
            app.welcome_model_selector.setCurrentText(target)
        saved = app.save_config()
        app._apply_live_style()
        font_changed = app.chat_font_size != old_font
        self.accept()
        if font_changed and not app._is_responding and app.current_session_id:
            app.load_session(app.current_session_id)
        if not saved:
            msg = "⚠ " + msg.replace("✓", "").strip() + " — but config file could not be written"
        app._toast.show(msg)
        QTimer.singleShot(50, app.open_settings_dialog)

    def _status(self, text: str, error: bool = False):
        self.status_label.setObjectName("StatusError" if error else "StatusSuccess")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {pal('danger') if error else pal('success')}; font-size: 12px;"
        )

    def _render_custom_models(self):
        while self.custom_models_box.count():
            item = self.custom_models_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self.working_custom_models:
            lbl = QLabel("No custom models yet.")
            lbl.setFont(_font(11))
            lbl.setStyleSheet(f"color: {pal('text_lo')};")
            self.custom_models_box.addWidget(lbl)
            return

        for i, cm in enumerate(self.working_custom_models):
            row = QFrame()
            row.setStyleSheet(
                f"background-color: {pal('bg_sidebar')}; border-radius: 8px;"
            )
            hl = QHBoxLayout(row)
            hl.setContentsMargins(10, 4, 6, 4)
            name = QLabel(cm["name"])
            name.setFont(_font(12))
            hl.addWidget(name, 1)
            edit_btn = QPushButton("✏️")
            edit_btn.setObjectName("IconBtn")
            edit_btn.setFixedSize(28, 28)
            edit_btn.clicked.connect(lambda _c=False, idx=i: self._edit_custom_model(idx))
            hl.addWidget(edit_btn)
            del_btn = QPushButton("🗑")
            del_btn.setObjectName("IconBtn")
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet(f"color: {pal('danger')};")
            del_btn.clicked.connect(lambda _c=False, idx=i: self._delete_custom_model(idx))
            hl.addWidget(del_btn)
            self.custom_models_box.addWidget(row)

    def _open_custom_dialog(self, cb, existing: dict | None = None):
        if self._custom_dialog is not None:
            try:
                if self._custom_dialog.isVisible():
                    self._custom_dialog.raise_()
                    self._custom_dialog.activateWindow()
                    return
            except RuntimeError:
                pass
        self._custom_dialog = CustomModelDialog(self, cb, existing=existing)
        self._custom_dialog.finished.connect(
            lambda _r: setattr(self, "_custom_dialog", None))
        self._custom_dialog.show()

    def _add_custom_model(self):
        def cb(data):
            if data["name"] in BASE_MODELS or any(
                c["name"] == data["name"] for c in self.working_custom_models
            ):
                QMessageBox.critical(
                    self, "Duplicate Name",
                    f"A model named '{data['name']}' already exists.")
                return False
            self.working_custom_models.append(data)
            self._render_custom_models()
            self._refresh_default_models()
            return True
        self._open_custom_dialog(cb)

    def _edit_custom_model(self, idx: int):
        existing = self.working_custom_models[idx]

        def cb(data):
            if data["name"] in BASE_MODELS or any(
                c["name"] == data["name"] for c in self.working_custom_models if c is not existing
            ):
                QMessageBox.critical(
                    self, "Duplicate Name",
                    f"A model named '{data['name']}' already exists.")
                return False
            old_name = existing["name"]
            self.working_custom_models[idx] = data
            if self.default_model_combo.currentText() == old_name:
                self.default_model_combo.setCurrentText(data["name"])
            self._render_custom_models()
            self._refresh_default_models()
            return True
        self._open_custom_dialog(cb, existing=existing)

    def _delete_custom_model(self, idx: int):
        name = self.working_custom_models[idx]["name"]
        reply = QMessageBox.question(
            self, "Delete", f"Remove custom model '{name}'?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.working_custom_models.pop(idx)
            self._render_custom_models()
            self._refresh_default_models()

    def _refresh_default_models(self):
        values = BASE_MODELS + [c["name"] for c in self.working_custom_models]
        cur = self.default_model_combo.currentText()
        self.default_model_combo.clear()
        self.default_model_combo.addItems(values)
        if cur in values:
            self.default_model_combo.setCurrentText(cur)
        else:
            self.default_model_combo.setCurrentText(
                self.app.default_model if self.app.default_model in values else BASE_MODELS[0])

    def _test_connection(self):
        if self._testing:
            return
        self._testing = True
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        self._status("Testing connections...", error=False)

        providers = [
            ("OpenAI",     self.openai_edit,     None),
            ("Gemini",     self.gemini_edit,     "genai"),
            ("OpenRouter", self.openrouter_edit, "https://openrouter.ai/api/v1"),
            ("Groq",       self.groq_edit,       "https://api.groq.com/openai/v1"),
        ]
        jobs = []
        for name, edit, base_url in providers:
            key = _clean_key(edit.text())
            if key:
                jobs.append((name, key, base_url))
        for cm in self.working_custom_models:
            key = (cm.get("api_key") or "").strip() or "no-key"
            jobs.append((cm["name"], key, cm.get("base_url", "")))

        if not jobs:
            self._testing = False
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test")
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
                            client = genai.Client(
                                api_key=key,
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

    def _on_test_done(self, ok: list[str], failed: list[str]):
        self._testing = False
        try:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test")
        except RuntimeError:
            return
        parts = []
        if ok:
            parts.append("✓ " + ", ".join(ok))
        if failed:
            parts.append("✗ Failed: " + ", ".join(failed))
        self._status("\n".join(parts), error=bool(failed))

    def _save(self):
        try:
            mt = int(self.max_tokens_edit.text().strip() or "0")
            hl = int(self.history_edit.text().strip() or "40")
            if mt < 0 or hl < 1:
                raise ValueError
        except ValueError:
            self.tabs.setCurrentIndex(1)
            self._status("✗ Max Tokens must be ≥ 0 and History Limit ≥ 1 (whole numbers).",
                         error=True)
            return

        if self.profile_edit.text().strip().upper() == "AI":
            self.tabs.setCurrentIndex(0)
            self._status("✗ 'AI' is reserved for the assistant - choose another profile name.",
                         error=True)
            return

        new_profile = self.profile_edit.text().strip()
        if new_profile and new_profile != self.app.profile_name:
            self.app.profile_name = new_profile
            self.app.profile_btn.setText(f"👤  {new_profile}")

        all_names = BASE_MODELS + [c["name"] for c in self.working_custom_models]
        chosen = self.default_model_combo.currentText()
        old_default = self.app.default_model
        self.app.default_model = chosen if chosen in all_names else BASE_MODELS[0]
        default_changed = self.app.default_model != old_default

        self.app.enter_sends = self.enter_sends_cb.isChecked()
        self.app.auto_scroll = self.auto_scroll_cb.isChecked()
        self.app.confirm_on_close = self.confirm_close_cb.isChecked()
        self.app.system_prompt = self.system_prompt_edit.toPlainText().strip()
        self.app.temperature = round(self.temp_slider.value() / 20.0, 2)
        self.app.top_p = round(self.top_p_slider.value() / 20.0, 2)
        max_tokens = min(int(self.max_tokens_edit.text().strip() or "0"), 1_000_000)
        history_limit = int(self.history_edit.text().strip() or "40")
        history_clamped = history_limit > 500
        self.app.max_tokens = max_tokens
        self.app.history_limit = min(history_limit, 500)

        new_mode = (self.theme_group.checkedButton().text().lower()
                    if self.theme_group.checkedButton() else "dark")
        self.app.appearance_mode = new_mode
        set_mode(new_mode)

        new_accent = self.accent_color
        if new_accent != self.app.accent_color:
            self.app.accent_color = new_accent
            PALETTE["accent"] = new_accent
            PALETTE["accent_dark"] = _darken(new_accent)

        new_font = int(self.font_slider.value())
        font_changed = new_font != self.app.chat_font_size
        self.app.chat_font_size = new_font
        CHAT_STYLE["size"] = new_font

        self.app.OPENAI_API_KEY = _clean_key(self.openai_edit.text())
        self.app.GEMINI_API_KEY = _clean_key(self.gemini_edit.text())
        self.app.OPENROUTER_API_KEY = _clean_key(self.openrouter_edit.text())
        self.app.GROQ_API_KEY = _clean_key(self.groq_edit.text())
        self.app.custom_models = [dict(c) for c in self.working_custom_models]

        _apply_theme(QApplication.instance())
        self.app._refresh_model_selectors()
        if default_changed and not self.app._is_responding:
            self.app.chat_model_selector.setCurrentText(self.app.default_model)
            self.app.welcome_model_selector.setCurrentText(self.app.default_model)

        saved = self.app.save_config()
        self.app._apply_live_style()
        if font_changed and not self.app._is_responding and self.app.current_session_id:
            self.app.load_session(self.app.current_session_id)

        if not saved:
            self.app._toast.show(
                "✗ Settings saved to memory, but could not write config file")
        elif history_clamped:
            self.app._toast.show("✓ Settings saved (History Limit capped to 500)")
        else:
            self.app._toast.show("✓ Settings saved")
        self.accept()


# ============================================================
# MAIN APPLICATION
# ============================================================
class ProjectKizenClient(QMainWindow):
    _ui_update_signal = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project-Kizen")
        w, h = _fit_window_size(1280, 800)
        self.resize(w, h)
        self.setMinimumSize(*_fit_window_size(1000, 700))

        self.current_session_id = None
        self.sidebar_expanded = True
        self._is_responding = False
        self._db_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._current_bubble: MessageBubble | None = None
        self._worker: threading.Thread | None = None
        self._prompt_history: list[str] = []
        self._last_scroll_time = 0.0
        self._scroll_pending = False
        self._welcome_state = None
        self._settings_dialog: SettingsDialog | None = None
        self._custom_dialog: CustomModelDialog | None = None
        self._autogrow_timers = {}
        self._save_config_timer = None

        cfg = self._load_config()
        self._apply_config_values(cfg)
        set_mode(self.appearance_mode)
        _apply_theme(QApplication.instance())

        self._ui_update_signal.connect(self._handle_ui_update)

        initial_model = self.default_model
        all_models = self._get_all_models()
        if initial_model not in all_models:
            initial_model = all_models[0]

        self._init_database()
        self._build_ui(initial_model)
        self._bind_shortcuts()

        self._toast = Toast(self)
        self._create_new_chat_internal()

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(50)
        self._scroll_timer.timeout.connect(self._tick_autoscroll)
        self._scroll_timer.start()

    # ---------------- config ----------------
    def _apply_config_values(self, cfg: dict):
        cfg = self._sanitize_config(cfg)
        self.OPENAI_API_KEY     = cfg.get("openai_key",     "ENTER_OPENAI_API_KEY_HERE")
        self.GEMINI_API_KEY     = cfg.get("gemini_key",     "ENTER_GEMINI_API_KEY_HERE")
        self.OPENROUTER_API_KEY = cfg.get("openrouter_key", "ENTER_OPENROUTER_API_KEY_HERE")
        self.GROQ_API_KEY       = cfg.get("groq_key",       "ENTER_GROQ_API_KEY_HERE")
        self.custom_models      = cfg.get("custom_models", [])

        self.profile_name     = cfg.get("profile", "Admin")
        self.default_model    = cfg.get("default_model", cfg.get("model", "Gemini 2.5 Flash"))
        known = BASE_MODELS + [c["name"] for c in self.custom_models]
        if self.default_model not in known:
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

    def _load_config(self) -> dict:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("config is not a JSON object")
            return data
        except FileNotFoundError:
            return {}
        except Exception:
            try:
                os.replace(CONFIG_PATH, CONFIG_PATH + ".bak")
            except OSError:
                pass
            return {}

    @staticmethod
    def _sanitize_config(cfg: dict) -> dict:
        cfg = dict(cfg) if isinstance(cfg, dict) else {}

        def num(key, cast, lo, hi, default):
            try:
                cfg[key] = min(hi, max(lo, cast(cfg.get(key, default))))
            except (TypeError, ValueError, OverflowError):
                cfg[key] = default

        num("temperature", float, 0.0, 2.0, 0.7)
        num("top_p", float, 0.0, 1.0, 1.0)
        num("max_tokens", int, 0, 1_000_000, 0)
        num("history_limit", int, 1, 500, HISTORY_LIMIT)
        num("chat_font_size", int, 11, 20, 14)

        for key, default in (("enter_sends", True), ("auto_scroll", True), ("confirm_on_close", True)):
            if not isinstance(cfg.get(key, default), bool):
                cfg[key] = default

        for key in ("profile", "system_prompt", "default_model", "model",
                    "openai_key", "gemini_key", "openrouter_key", "groq_key"):
            if key in cfg and not isinstance(cfg[key], str):
                cfg.pop(key)

        if "profile" in cfg:
            prof = cfg["profile"].strip()
            if prof and prof.upper() != "AI":
                cfg["profile"] = prof
            else:
                cfg.pop("profile")

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
            if not isinstance(c, dict):
                continue
            item = {k: str(c.get(k) or "").strip()
                    for k in ("name", "base_url", "api_key", "model_id")}
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

    def _config_dict(self) -> dict:
        model = (self.chat_model_selector.currentText()
                 if hasattr(self, "chat_model_selector") else self.default_model)
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

    def save_config(self) -> bool:
        tmp = CONFIG_PATH + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._config_dict(), f, indent=2)
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, CONFIG_PATH)
            return True
        except Exception:
            traceback.print_exc()
            try:
                os.remove(tmp)
            except OSError:
                pass
            return False

    def _apply_live_style(self):
        if not self._is_responding and hasattr(self, "send_btn"):
            self.send_btn.setStyleSheet(
                f"background-color: {pal('accent')}; color: #000; "
                f"border-radius: 20px; font-weight: bold; text-align: center;"
            )

    def _get_all_models(self) -> list[str]:
        return BASE_MODELS + [cm["name"] for cm in self.custom_models]

    def _refresh_model_selectors(self):
        all_models = self._get_all_models()
        if self.default_model not in all_models:
            self.default_model = all_models[0]
        for combo in (self.chat_model_selector, self.welcome_model_selector):
            cur = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(all_models)
            combo.setCurrentText(cur if cur in all_models else self.default_model)
            combo.blockSignals(False)

    # ---------------- database ----------------
    def _init_database(self):
        try:
            os.makedirs(_KIZEN_DIR, exist_ok=True)
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self.cursor = self.conn.cursor()
            with self._db_lock:
                try:
                    self.cursor.execute("PRAGMA journal_mode=WAL")
                    self.cursor.execute("PRAGMA synchronous=NORMAL")
                    self.cursor.execute("PRAGMA foreign_keys=ON")
                except sqlite3.DatabaseError:
                    pass
                self.cursor.execute(
                    "CREATE TABLE IF NOT EXISTS sessions "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT)")
                self.cursor.execute(
                    "CREATE TABLE IF NOT EXISTS messages "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, "
                    "sender TEXT, message TEXT, model TEXT, "
                    "FOREIGN KEY(session_id) REFERENCES sessions(id))")
                self.cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_messages_session "
                    "ON messages(session_id, id)")
                self.cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_id "
                    "ON sessions(id DESC)")
                self.cursor.execute(
                    "DELETE FROM sessions WHERE id NOT IN "
                    "(SELECT DISTINCT session_id FROM messages WHERE session_id IS NOT NULL)")
                self.conn.commit()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(
                None, "Database Error",
                f"Could not initialize database at:\n{DB_PATH}\n\n{e}")
            sys.exit(1)

    # ---------------- UI ----------------
    def _build_ui(self, initial_model: str):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self._build_sidebar()
        self.icon_sidebar = self._build_icon_sidebar()
        self.icon_sidebar.setVisible(False)

        root.addWidget(self.sidebar)
        root.addWidget(self.icon_sidebar)

        self.main_area = self._build_main_area(initial_model)
        root.addWidget(self.main_area, 1)

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(260)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        top = QWidget()
        hl = QHBoxLayout(top)
        hl.setContentsMargins(15, 15, 15, 15)
        title = QLabel("⚡ Project-Kizen")
        title.setFont(_font(18, bold=True))
        hl.addWidget(title)
        hl.addStretch(1)
        collapse_btn = QPushButton("◫")
        collapse_btn.setObjectName("IconBtn")
        collapse_btn.setFixedSize(36, 36)
        collapse_btn.setToolTip("Close sidebar")
        collapse_btn.clicked.connect(self.toggle_sidebar)
        hl.addWidget(collapse_btn)
        v.addWidget(top)

        menu = QWidget()
        ml = QVBoxLayout(menu)
        ml.setContentsMargins(10, 0, 10, 10)
        ml.setSpacing(2)
        new_btn = QPushButton("✏️  New chat")
        new_btn.setFixedHeight(40)
        new_btn.clicked.connect(self.create_new_chat)
        ml.addWidget(new_btn)
        v.addWidget(menu)

        hist = QWidget()
        hl2 = QVBoxLayout(hist)
        hl2.setContentsMargins(10, 0, 10, 0)
        hl2.setSpacing(2)
        sec = QLabel("All")
        sec.setObjectName("SidebarHeader")
        hl2.addWidget(sec)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_content = QWidget()
        self.history_layout = QVBoxLayout(self.history_content)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(2)
        self.history_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.history_content)
        hl2.addWidget(scroll, 1)
        v.addWidget(hist, 1)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(15, 15, 15, 15)
        self.profile_btn = QPushButton(f"👤  {self.profile_name}")
        self.profile_btn.setFixedHeight(40)
        self.profile_btn.setFont(_font(13, bold=True))
        self.profile_btn.setStyleSheet(
            "background: transparent; border: none; text-align: left; padding: 6px 12px;")
        self.profile_btn.clicked.connect(self.open_profile_dialog)
        bl.addWidget(self.profile_btn, 1)
        settings_btn = QPushButton("⚙️")
        settings_btn.setObjectName("IconBtn")
        settings_btn.setFixedSize(40, 40)
        settings_btn.clicked.connect(self.open_settings_dialog)
        bl.addWidget(settings_btn)
        v.addWidget(bottom)

        return side

    def _build_icon_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("IconSidebar")
        side.setFixedWidth(70)
        v = QVBoxLayout(side)
        v.setContentsMargins(0, 15, 0, 15)
        v.setSpacing(8)
        v.setAlignment(Qt.AlignHCenter)

        expand_btn = QPushButton("◫")
        expand_btn.setObjectName("IconBtn")
        expand_btn.setFixedSize(44, 44)
        expand_btn.setToolTip("Open sidebar")
        expand_btn.clicked.connect(self.toggle_sidebar)
        v.addWidget(expand_btn, 0, Qt.AlignHCenter)

        new_btn = QPushButton("✏️")
        new_btn.setObjectName("IconBtn")
        new_btn.setFixedSize(44, 44)
        new_btn.setToolTip("New chat")
        new_btn.clicked.connect(self.create_new_chat)
        v.addWidget(new_btn, 0, Qt.AlignHCenter)

        v.addStretch(1)

        set_btn = QPushButton("⚙️")
        set_btn.setObjectName("IconBtn")
        set_btn.setFixedSize(44, 44)
        set_btn.setToolTip("Settings")
        set_btn.clicked.connect(self.open_settings_dialog)
        v.addWidget(set_btn, 0, Qt.AlignHCenter)

        prof_btn = QPushButton("👤")
        prof_btn.setObjectName("IconBtn")
        prof_btn.setFixedSize(44, 44)
        prof_btn.setToolTip("Account")
        prof_btn.clicked.connect(self.open_profile_dialog)
        v.addWidget(prof_btn, 0, Qt.AlignHCenter)

        return side

    def _build_main_area(self, initial_model: str) -> QWidget:
        area = QWidget()
        v = QVBoxLayout(area)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        top = QWidget()
        top.setFixedHeight(60)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(20, 0, 20, 0)
        self.top_title = QLabel("New Chat")
        self.top_title.setFont(_font(18, bold=True))
        tl.addWidget(self.top_title)
        tl.addStretch(1)
        v.addWidget(top)
        self.top_bar = top

        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)

        self.welcome_page = self._build_welcome_page(initial_model)
        self.stack.addWidget(self.welcome_page)

        self.chat_page = self._build_chat_page()
        self.stack.addWidget(self.chat_page)

        self.input_container = QWidget()
        il = QHBoxLayout(self.input_container)
        il.setContentsMargins(180, 0, 180, 30)
        self.chat_input_frame = self._build_input_frame(initial_model, send_from_welcome=False)
        il.addWidget(self.chat_input_frame)
        v.addWidget(self.input_container)

        return area

    def _build_welcome_page(self, initial_model: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.addStretch(1)

        icon = QLabel("⚡")
        icon.setFont(_font(50))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"color: {pal('accent')};")
        v.addWidget(icon)

        title = QLabel("Where should we start?")
        title.setFont(_font(32))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {pal('text_mid')};")
        v.addWidget(title)

        v.addSpacing(40)

        self.welcome_input_frame = self._build_input_frame(initial_model, send_from_welcome=True)
        row = QHBoxLayout()
        row.setContentsMargins(180, 0, 180, 0)
        row.addWidget(self.welcome_input_frame)
        v.addLayout(row)

        v.addStretch(2)
        return page

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(0, 0, 0, 20)
        self.chat_layout.setSpacing(4)
        self.chat_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.chat_content)
        v.addWidget(scroll)
        self.chat_scroll = scroll
        return page

    def _build_input_frame(self, initial_model: str, send_from_welcome: bool) -> QFrame:
        frame = QFrame()
        frame.setObjectName("InputFrame")
        frame.setFixedHeight(60)

        hl = QHBoxLayout(frame)
        hl.setContentsMargins(10, 10, 10, 10)
        hl.setSpacing(6)

        plus = QPushButton("＋")
        plus.setObjectName("IconBtn")
        plus.setFixedSize(40, 40)
        plus.setFont(_font(18))
        target_input_attr = "welcome_input" if send_from_welcome else "prompt_input"
        plus.clicked.connect(
            lambda _c=False, t=target_input_attr, w=plus: self._show_prompt_history(w, t))
        hl.addWidget(plus)

        text_input = QTextEdit()
        text_input.setObjectName("TransparentInput")
        text_input.setPlaceholderText("Ask Project-Kizen")
        text_input.setFixedHeight(32)
        text_input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text_input.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text_input.setFont(_font(15))
        text_input.setFrameShape(QFrame.NoFrame)
        text_input.textChanged.connect(
            lambda t=text_input, f=frame: self._autogrow_input(t, f))

        if send_from_welcome:
            self.welcome_input = text_input
            text_input.installEventFilter(self)
        else:
            self.prompt_input = text_input
            text_input.installEventFilter(self)
        hl.addWidget(text_input, 1)

        model_combo = QComboBox()
        model_combo.setFixedHeight(36)
        model_combo.setFixedWidth(170)
        model_combo.addItems(self._get_all_models())
        model_combo.setCurrentText(initial_model)
        hl.addWidget(model_combo)

        send_btn = QPushButton("↑")
        send_btn.setObjectName("SendBtn")
        send_btn.setFixedSize(40, 40)
        send_btn.setFont(_font(16, bold=True))

        if send_from_welcome:
            self.welcome_model_selector = model_combo
            self.welcome_send_btn = send_btn
            send_btn.clicked.connect(self._send_from_welcome)
            model_combo.currentTextChanged.connect(self._on_welcome_model_change)
        else:
            self.chat_model_selector = model_combo
            self.send_btn = send_btn
            self.model_selector = model_combo
            send_btn.clicked.connect(self.send_message)
            model_combo.currentTextChanged.connect(self._on_model_change)
            self.chat_input_frame = frame

        hl.addWidget(send_btn)
        return frame

    # ---------------- model synchronization ----------------
    def _sync_and_save_model(self, source_combo: QComboBox, target_combo: QComboBox):
        new_model = source_combo.currentText()
        if not new_model:
            return
        if new_model == target_combo.currentText() and new_model == self.default_model:
            return
        target_combo.blockSignals(True)
        target_combo.setCurrentText(new_model)
        target_combo.blockSignals(False)
        self.default_model = new_model

        if not self._save_config_timer:
            self._save_config_timer = QTimer(self)
            self._save_config_timer.setSingleShot(True)
            self._save_config_timer.setInterval(500)
            self._save_config_timer.timeout.connect(self._delayed_save_config)
        self._save_config_timer.start()

    def _delayed_save_config(self):
        if not self.save_config():
            self._toast.show("✗ Model selected but config could not be saved")

    def _on_model_change(self, _val: str | None = None):
        self._sync_and_save_model(self.chat_model_selector, self.welcome_model_selector)

    def _on_welcome_model_change(self, _val: str | None = None):
        self._sync_and_save_model(self.welcome_model_selector, self.chat_model_selector)

    # ---------------- thread ↔ UI ----------------
    def _post_ui(self, callback, *args):
        self._ui_update_signal.emit(callback, args)

    @Slot(object, object)
    def _handle_ui_update(self, callback, args):
        try:
            callback(*args)
        except Exception:
            traceback.print_exc()

    # ---------------- sidebar toggle ----------------
    def toggle_sidebar(self):
        if self.sidebar_expanded:
            self.sidebar.setVisible(False)
            self.icon_sidebar.setVisible(True)
            self.sidebar_expanded = False
        else:
            self.icon_sidebar.setVisible(False)
            self.sidebar.setVisible(True)
            self.sidebar_expanded = True

    # ---------------- welcome vs chat ----------------
    def _set_welcome_visible(self, visible: bool):
        if self._welcome_state == visible:
            return
        self._welcome_state = visible
        self.stack.setCurrentIndex(0 if visible else 1)
        self.top_bar.setVisible(not visible)
        self.input_container.setVisible(not visible)

    # ---------------- session list ----------------
    def load_sessions_list(self, filter_text: str = ""):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        with self._db_lock:
            if filter_text:
                self.cursor.execute(
                    "SELECT id, title, created_at FROM sessions "
                    "WHERE LOWER(title) LIKE ? ORDER BY id DESC LIMIT ?",
                    (f"%{filter_text.lower()}%", SESSION_LIMIT))
            else:
                self.cursor.execute(
                    "SELECT id, title, created_at FROM sessions "
                    "ORDER BY id DESC LIMIT ?", (SESSION_LIMIT,))
            sessions = self.cursor.fetchall()

        for sid, title, _created in sessions:
            self._build_session_row(sid, title)

    def _build_session_row(self, session_id: int, title: str):
        is_active = (session_id == self.current_session_id)
        row = QFrame()
        if is_active:
            row.setStyleSheet(
                f"background-color: {pal('bg_sidebar_2')}; border-radius: 20px;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(4, 2, 4, 2)
        hl.setSpacing(2)

        shown = (title or "").replace("\n", " ")
        if len(shown) > 26:
            shown = shown[:25] + "…"
        btn = QPushButton(shown)
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            "background: transparent; border: none; text-align: left; "
            "padding: 4px 10px; border-radius: 18px;")
        btn.clicked.connect(lambda _c=False, sid=session_id: self.load_session(sid))
        hl.addWidget(btn, 1)

        dots = QPushButton("...")
        dots.setObjectName("IconBtn")
        dots.setFixedSize(28, 28)
        dots.clicked.connect(
            lambda _c=False, sid=session_id, t=title, b=dots:
                self._show_chat_menu(sid, t, b))
        hl.addWidget(dots)

        self.history_layout.addWidget(row)

    def _show_chat_menu(self, session_id: int, title: str, widget: QWidget):
        menu = QMenu(self)
        menu.addAction("✏️  Rename",
                       lambda: self._edit_chat_title(session_id, title))
        menu.addAction("🗑️  Delete",
                       lambda: self.delete_session(session_id))
        menu.exec(widget.mapToGlobal(widget.rect().bottomLeft()))

    def _edit_chat_title(self, session_id: int, title: str):
        dlg = EditChatDialog(self, title,
                             lambda n: self.rename_session(session_id, n))
        dlg.exec()

    def _drop_session_if_empty(self, session_id: int | None):
        if session_id is None:
            return
        with self._db_lock:
            self.cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                self.conn.commit()

    def load_session(self, session_id: int):
        if self._is_responding:
            return
        if session_id != self.current_session_id:
            self._drop_session_if_empty(self.current_session_id)
        self.current_session_id = session_id

        with self._db_lock:
            self.cursor.execute(
                "SELECT sender, message, model FROM messages "
                "WHERE session_id = ? ORDER BY id", (session_id,))
            messages = self.cursor.fetchall()
            self.cursor.execute(
                "SELECT title FROM sessions WHERE id = ?", (session_id,))
            row = self.cursor.fetchone()

        self.clear_chat_display()
        self.chat_content.setUpdatesEnabled(False)
        try:
            for sender, msg, model in messages:
                self._add_bubble(sender=sender, text=msg, model=model,
                                 is_user=(sender != "AI"), scroll=False)
        finally:
            self.chat_content.setUpdatesEnabled(True)
            self.chat_content.update()

        if not messages:
            self._set_welcome_visible(True)
        else:
            self._set_welcome_visible(False)

        if row:
            self.top_title.setText(row[0])
        self.load_sessions_list()
        self._scroll_to_bottom(force=True)

    def rename_session(self, session_id: int, new_title: str):
        with self._db_lock:
            self.cursor.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
            self.conn.commit()
        if session_id == self.current_session_id:
            self.top_title.setText(new_title)
        self.load_sessions_list()

    def delete_session(self, session_id: int):
        if self._is_responding:
            return
        reply = QMessageBox.question(
            self, "Delete", "Are you sure you want to delete this chat?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        with self._db_lock:
            self.cursor.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,))
            self.cursor.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,))
            self.conn.commit()
        if self.current_session_id == session_id:
            self._create_new_chat_internal()
        else:
            self.load_sessions_list()

    def clear_chat_display(self):
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._current_bubble = None

    # ---------------- bubbles ----------------
    def _add_bubble(self, sender: str, text: str, model: str | None = None,
                    is_user: bool = False, scroll: bool = True) -> MessageBubble:
        bubble = MessageBubble(self.chat_content, sender=sender, text=text,
                               model=model, is_user=is_user,
                               chat_font_size=self.chat_font_size)
        self.chat_layout.addWidget(bubble)
        if scroll:
            self._scroll_to_bottom(force=True)
        return bubble

    # ---------------- new chat ----------------
    def create_new_chat(self):
        if self._is_responding:
            return
        self._create_new_chat_internal()

    def _create_new_chat_internal(self):
        if self.current_session_id is not None:
            with self._db_lock:
                self.cursor.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                    (self.current_session_id,))
                if self.cursor.fetchone()[0] == 0:
                    self.cursor.execute(
                        "DELETE FROM sessions WHERE id = ?",
                        (self.current_session_id,))
                    self.conn.commit()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._db_lock:
            self.cursor.execute(
                "INSERT INTO sessions (title, created_at) VALUES (?, ?)",
                ("New Chat", timestamp))
            self.conn.commit()
            self.current_session_id = self.cursor.lastrowid
        self.clear_chat_display()
        self._set_welcome_visible(True)
        self.top_title.setText("New Chat")
        self.load_sessions_list()

    # ---------------- send ----------------
    def _send_from_welcome(self):
        if self._is_responding:
            return
        text = self.welcome_input.toPlainText().strip()
        if not text:
            return
        self.prompt_input.setPlainText(text)
        self.welcome_input.clear()
        self.welcome_input.setFixedHeight(32)
        self.welcome_input_frame.setFixedHeight(60)
        self.send_message()

    def send_message(self):
        if self._is_responding:
            return
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return
        if not self._prompt_history or self._prompt_history[-1] != prompt:
            self._prompt_history.append(prompt)
        self._prompt_history = self._prompt_history[-50:]

        model = self.chat_model_selector.currentText()
        self.prompt_input.clear()
        self.prompt_input.setFixedHeight(32)
        self.chat_input_frame.setFixedHeight(60)

        self._set_welcome_visible(False)
        self._add_bubble(sender=self.profile_name, text=prompt, is_user=True)
        self.save_message_to_db(self.profile_name, prompt)
        self._auto_title(prompt)
        ai_bubble = self._add_bubble(sender=model, text="▌ Thinking...",
                                     model=model, is_user=False)
        self._current_bubble = ai_bubble
        session_id = self.current_session_id

        self._stop_event.clear()
        self._is_responding = True
        self._set_send_button_active(True)
        self._worker = threading.Thread(
            target=self._fetch_response, args=(model, session_id), daemon=True)
        self._worker.start()

    def _set_send_button_active(self, active: bool):
        btn = self.send_btn
        if not btn:
            return
        if active:
            btn.setText("■")
            btn.setStyleSheet(
                f"background-color: {pal('danger')}; color: #000; "
                f"border-radius: 20px; font-weight: bold; text-align: center;")
            try:
                btn.clicked.disconnect()
            except Exception:
                pass
            btn.clicked.connect(self.stop_response)
        else:
            btn.setText("↑")
            btn.setStyleSheet(
                f"background-color: {pal('accent')}; color: #000; "
                f"border-radius: 20px; font-weight: bold; text-align: center;")
            try:
                btn.clicked.disconnect()
            except Exception:
                pass
            btn.clicked.connect(self.send_message)

    def _auto_title(self, prompt: str):
        with self._db_lock:
            self.cursor.execute(
                "SELECT title FROM sessions WHERE id = ?",
                (self.current_session_id,))
            row = self.cursor.fetchone()
        if row and row[0] == "New Chat":
            title = prompt.replace("\n", " ")
            title = title[:40] + ("…" if len(title) > 40 else "")
            self.rename_session(self.current_session_id, title)

    def stop_response(self):
        if self._is_responding:
            self._stop_event.set()

    # ---------------- streaming ----------------
    def _fetch_response(self, model: str, session_id: int):
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
            if buffer:
                self._post_ui(self._append_chunk, buffer)
            if self._stop_event.is_set():
                stopped = True
        except Exception as e:
            err = f"\n\n⚠️ Error: {e}"
            response_text += err
            self._post_ui(self._append_chunk, err)
            traceback.print_exc()
        finally:
            if buffer:
                self._post_ui(self._append_chunk, buffer)
            if stopped:
                response_text += " [stopped]"
                self._post_ui(self._append_chunk, " [stopped]")
            if response_text:
                try:
                    self.save_message_to_db("AI", response_text, model, session_id)
                except Exception:
                    traceback.print_exc()
            self._post_ui(self._on_response_finished)

    def _append_chunk(self, text: str):
        if self._current_bubble:
            if self._current_bubble._raw_text == "▌ Thinking...":
                self._current_bubble.reset()
                self._current_bubble._raw_text = ""
            self._current_bubble.append_text(text)
            self._scroll_to_bottom()

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
            self._set_send_button_active(False)
        self.prompt_input.setFocus()
        self._scroll_to_bottom(force=True)

    def _build_gen_config(self) -> dict:
        kw = {}
        if self.temperature is not None:
            kw["temperature"] = self.temperature
        if self.max_tokens and self.max_tokens > 0:
            kw["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            kw["top_p"] = self.top_p
        return kw

    def _stream_gemini(self, model: str, history: list[dict]):
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

        gen = client.models.generate_content_stream(**kwargs)
        try:
            for chunk in gen:
                if self._stop_event.is_set():
                    break
                if getattr(chunk, "text", None):
                    yield chunk.text
        finally:
            close_fn = getattr(gen, "close", None)
            if close_fn:
                try:
                    close_fn()
                except Exception:
                    pass

    def _stream_openai_compatible(self, api_key: str, base_url: str | None, model_id: str, history: list[dict]):
        client = (OpenAI(api_key=api_key, base_url=base_url)
                  if base_url else OpenAI(api_key=api_key))
        messages = history
        if self.system_prompt:
            messages = [{"role": "system", "content": self.system_prompt}] + messages
        kwargs = {"model": model_id, "messages": messages, "stream": True}
        kwargs.update(self._build_gen_config())
        stream = client.chat.completions.create(**kwargs)
        try:
            for chunk in stream:
                if self._stop_event.is_set():
                    break
                if (chunk.choices and chunk.choices[0].delta
                        and chunk.choices[0].delta.content):
                    yield chunk.choices[0].delta.content
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _stream_response(self, model: str, session_id: int):
        history = self._get_chat_history(session_id)
        if not history:
            raise RuntimeError("History is empty.")

        if model in GEMINI_MODEL_MAP:
            yield from self._stream_gemini(model, history)
            return

        providers = [
            (OPENAI_MODEL_MAP,     self.OPENAI_API_KEY,     None,                             "OpenAI"),
            (OPENROUTER_MODEL_MAP, self.OPENROUTER_API_KEY, "https://openrouter.ai/api/v1",    "OpenRouter"),
            (GROQ_MODEL_MAP,       self.GROQ_API_KEY,       "https://api.groq.com/openai/v1", "Groq"),
        ]
        for model_map, api_key, base_url, provider_name in providers:
            if model in model_map:
                if not api_key or api_key.startswith("ENTER_"):
                    raise RuntimeError(f"Missing {provider_name} API key.")
                yield from self._stream_openai_compatible(
                    api_key, base_url, model_map[model], history)
                return

        cm = next((c for c in self.custom_models if c["name"] == model), None)
        if cm:
            yield from self._stream_openai_compatible(
                cm.get("api_key") or "no-key",
                cm["base_url"], cm["model_id"], history)
            return

        raise ValueError(f"Unknown model: {model}")

    # ---------------- db helpers ----------------
    def save_message_to_db(self, sender: str, message: str, model: str | None = None,
                           session_id: int | None = None):
        sid = session_id or self.current_session_id
        if not sid:
            return
        with self._db_lock:
            self.cursor.execute(
                "INSERT INTO messages (session_id, sender, message, model) "
                "VALUES (?, ?, ?, ?)",
                (sid, sender, message, model))
            self.conn.commit()

    def _get_chat_history(self, session_id: int) -> list[dict]:
        limit = max(1, int(self.history_limit or HISTORY_LIMIT))
        with self._db_lock:
            self.cursor.execute(
                "SELECT sender, message FROM messages WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ?", (session_id, limit))
            rows = self.cursor.fetchall()[::-1]
        history = []
        for s, m in rows:
            if s == "AI":
                m = re.sub(r"\n\n⚠️ Error: [\s\S]*$", "", m or "")
                m = re.sub(r" \[stopped\]$", "", m).strip()
                if not m:
                    m = "(no response)"
            history.append({
                "role": "assistant" if s == "AI" else "user",
                "content": m,
            })
        while len(history) > 1 and history[0]["role"] == "assistant":
            history.pop(0)
        return history

    # ---------------- dialogs / misc ----------------
    def open_profile_dialog(self):
        dlg = ProfileDialog(self, self.profile_name, self.update_profile_name)
        dlg.exec()

    def open_settings_dialog(self):
        if self._settings_dialog is not None:
            try:
                if self._settings_dialog.isVisible():
                    self._settings_dialog.raise_()
                    self._settings_dialog.activateWindow()
                    return
            except RuntimeError:
                pass
        self._settings_dialog = SettingsDialog(self, self)
        self._settings_dialog.show()

    def update_profile_name(self, new_name: str):
        if new_name.strip().upper() == "AI":
            self._toast.show("✗ 'AI' is a reserved name")
            return
        self.profile_name = new_name
        self.profile_btn.setText(f"👤  {self.profile_name}")
        self.save_config()

    # ---------------- input auto-grow ----------------
    def _autogrow_input(self, text_input: QTextEdit, frame: QFrame):
        if text_input not in self._autogrow_timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(50)
            timer.timeout.connect(lambda: self._perform_autogrow(text_input, frame))
            self._autogrow_timers[text_input] = timer

        self._autogrow_timers[text_input].start()

    def _perform_autogrow(self, text_input: QTextEdit, frame: QFrame):
        text = text_input.toPlainText()
        lines = text.count("\n") + 1
        # Fast approximation: ~22px per line + padding
        new_h = max(32, min(152, lines * 22 + 10))
        if text_input.height() == new_h:
            return
        text_input.setFixedHeight(new_h)
        frame.setFixedHeight(new_h + 28)

    # ---------------- input key handling ----------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.KeyPress:
            is_prompt = getattr(self, "prompt_input", None) is obj
            is_welcome = getattr(self, "welcome_input", None) is obj
            if is_prompt or is_welcome:
                key = event.key()
                mods = event.modifiers()
                if key in (Qt.Key_Return, Qt.Key_Enter):
                    if mods & Qt.ShiftModifier:
                        return False  # Shift+Enter => newline
                    if not (mods & Qt.ControlModifier) and not self.enter_sends:
                        return False  # Enter alone, enter_sends=False => newline
                    if is_welcome:
                        self._send_from_welcome()
                    else:
                        self.send_message()
                    return True
                if key == Qt.Key_Up and not (mods & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier)):
                    if not obj.toPlainText().strip() and self._prompt_history:
                        obj.setPlainText(self._prompt_history[-1])
                        cur = obj.textCursor()
                        cur.movePosition(QTextCursor.End)
                        obj.setTextCursor(cur)
                        return True
        return super().eventFilter(obj, event)

    def _show_prompt_history(self, anchor_widget: QWidget, target_attr: str):
        target = getattr(self, target_attr, None)
        if target is None:
            return
        menu = QMenu(self)
        items = self._prompt_history[-20:]
        if not items:
            act = menu.addAction("(no history)")
            act.setEnabled(False)
        else:
            for p in reversed(items):
                label = p.replace("\n", " ")
                if len(label) > 60:
                    label = label[:60] + "…"
                menu.addAction(label, lambda t=p: self._insert_prompt(t, target))
        menu.exec(anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft()))

    def _insert_prompt(self, text: str, target: QTextEdit):
        target.setPlainText(text)
        target.setFocus()
        cur = target.textCursor()
        cur.movePosition(QTextCursor.End)
        target.setTextCursor(cur)

    # ---------------- scroll ----------------
    def _scroll_to_bottom(self, force: bool = False):
        if not force and not self.auto_scroll:
            return
        bar = self.chat_scroll.verticalScrollBar()
        if not force:
            if bar.value() < bar.maximum() - 20:
                return
            now = time.monotonic()
            if now - self._last_scroll_time < 0.05:
                return
            self._last_scroll_time = now
        
        if self._scroll_pending:
            return
        self._scroll_pending = True
        def _do_scroll():
            self._scroll_pending = False
            bar.setValue(bar.maximum())
        QTimer.singleShot(10, _do_scroll)

    def _tick_autoscroll(self):
        if self._is_responding and self.auto_scroll:
            self._scroll_to_bottom()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_toast") and self._toast.isVisible():
            x = (self.width() - self._toast.width()) // 2
            self._toast.move(max(0, x), int(self.height() * 0.04))

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self.create_new_chat)
        QShortcut(QKeySequence("Ctrl+,"), self, self.open_settings_dialog)
        QShortcut(QKeySequence("Escape"), self,
                  lambda: self.stop_response() if self._is_responding else None)

    # ---------------- window close ----------------
    def closeEvent(self, event):
        open_dialogs = []
        for attr, label in (("_settings_dialog", "Settings"),
                            ("_custom_dialog", "Custom Model")):
            dlg = getattr(self, attr, None)
            if dlg is None:
                continue
            try:
                if dlg.isVisible():
                    open_dialogs.append(label)
            except RuntimeError:
                pass
        if open_dialogs:
            reply = QMessageBox.question(
                self, "Unsaved changes",
                f"Unsaved changes will be lost in: {', '.join(open_dialogs)}.\n"
                "Continue closing?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        if self.confirm_on_close:
            reply = QMessageBox.question(
                self, "Exit", "Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                event.ignore()
                return

        self._stop_event.set()
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=3)
            if self._worker.is_alive():
                self._worker.join(timeout=2)
        if not self.save_config():
            try:
                QMessageBox.warning(
                    self, "Config not saved",
                    "Settings could not be written to disk.\n"
                    "Changes will only apply to this session.")
            except Exception:
                traceback.print_exc()
        worker_alive = self._worker is not None and self._worker.is_alive()
        if not worker_alive:
            try:
                self.conn.close()
            except Exception:
                traceback.print_exc()
        event.accept()


# ============================================================
# ENTRY
# ============================================================
def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Project-Kizen")
    app.setFont(_font(12))
    window = ProjectKizenClient()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()