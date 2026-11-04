import queue
import sqlite3
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from google import genai
from openai import OpenAI

# ------------------- THEME -------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ------------------- CONSTANTS -------------------
SEPARATOR = "-" * 40
GEMINI_MODEL_MAP = {
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "Gemini 2.5 Pro":   "gemini-2.5-pro",
}
OPENAI_MODEL_MAP = {
    "GPT-4o-mini": "gpt-4o-mini",
    "GPT-4o":      "gpt-4o",
}


# ============================================================
# DIALOGS
# ============================================================

class _TextInputDialog(ctk.CTkToplevel):
    """Generic dialog for editing a single text value."""
    TITLE = ""
    GEOMETRY = "350x200"
    HEADER = ""
    PLACEHOLDER = ""
    SAVE_LABEL = "Save"

    def __init__(self, parent, current_value, callback):
        super().__init__(parent)
        self.title(self.TITLE)
        self.geometry(self.GEOMETRY)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.callback = callback

        ctk.CTkLabel(
            self, text=self.HEADER, font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(15, 10))

        self.entry = ctk.CTkEntry(self, placeholder_text=self.PLACEHOLDER, width=250)
        self.entry.insert(0, current_value)
        self.entry.pack(pady=10)
        self.entry.bind("<Return>", lambda _e: self._save())

        ctk.CTkButton(self, text=self.SAVE_LABEL, command=self._save).pack(pady=15)
        self.entry.focus_set()

    def _save(self):
        value = self.entry.get().strip()
        if value:
            self.callback(value)
        self.destroy()


class ProfileDialog(_TextInputDialog):
    TITLE = "Edit Profile"
    GEOMETRY = "350x220"
    HEADER = "Profile Settings"
    PLACEHOLDER = "Enter Profile Name"
    SAVE_LABEL = "Save Changes"


class EditChatDialog(_TextInputDialog):
    TITLE = "Rename Chat"
    GEOMETRY = "350x200"
    HEADER = "Edit Chat Title"
    PLACEHOLDER = "Enter New Chat Title"
    SAVE_LABEL = "Save"


class SettingsDialog(ctk.CTkToplevel):
    """Application settings dialog."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("Project-Kizen Settings")
        self.geometry("450x400")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.app = app

        ctk.CTkLabel(
            self, text="Settings & Configurations",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 15))

        api_frame = ctk.CTkFrame(self)
        api_frame.pack(fill="x", padx=20, pady=10)
        self.openai_entry = self._add_key_field(api_frame, "OpenAI API Key:", app.OPENAI_API_KEY)
        self.gemini_entry = self._add_key_field(api_frame, "Gemini API Key:", app.GEMINI_API_KEY)

        theme_frame = ctk.CTkFrame(self)
        theme_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(theme_frame, text="Appearance Mode:", font=ctk.CTkFont(size=12)).pack(
            side="left", padx=15, pady=15
        )
        self.theme_menu = ctk.CTkOptionMenu(
            theme_frame, values=["Dark", "Light", "System"], command=ctk.set_appearance_mode
        )
        self.theme_menu.pack(side="right", padx=15, pady=15)
        self.theme_menu.set(ctk.get_appearance_mode())

        ctk.CTkButton(
            self, text="Save & Close", fg_color="green", command=self._save
        ).pack(pady=15)

    @staticmethod
    def _add_key_field(parent, label, value):
        ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=10, pady=(5, 0)
        )
        entry = ctk.CTkEntry(parent, width=380, show="*")
        entry.insert(0, value)
        entry.pack(padx=10, pady=5)
        return entry

    def _save(self):
        self.app.OPENAI_API_KEY = self.openai_entry.get().strip()
        self.app.GEMINI_API_KEY = self.gemini_entry.get().strip()
        self.destroy()


# ============================================================
# MAIN APPLICATION
# ============================================================

class ProjectKizenClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Project-Kizen-Client")
        self.geometry("1100x700")
        self.minsize(900, 600)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------- state ----------
        self.profile_name = "Admin"
        self.current_session_id = None
        self.sidebar_visible = True
        self._is_responding = False
        self._db_lock = threading.Lock()
        self._ui_queue = queue.Queue()

        # ---------- API keys (replace via Settings dialog) ----------
        self.OPENAI_API_KEY = "ENTER_OPENAI_API_KEY_HERE"
        self.GEMINI_API_KEY = "ENTER_GEMINI_API_KEY_HERE"

        # ---------- init ----------
        self._init_database()
        self._build_sidebar()
        self._build_main_area()

        self.load_sessions_list()
        self.create_new_chat()

        self._poll_ui_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(3, weight=1)

        self.logo_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="⚡ Project-Kizen ◀",
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color="transparent",
            hover_color=("#333333", "#222222"),
            anchor="w",
            command=self.toggle_sidebar,
        )
        self.logo_btn.grid(row=0, column=0, padx=15, pady=(20, 10), sticky="ew")

        self.new_chat_btn = ctk.CTkButton(
            self.sidebar_frame, text="+ New chat",
            fg_color="transparent", border_width=1, anchor="w",
            command=self.create_new_chat,
        )
        self.new_chat_btn.grid(row=1, column=0, padx=15, pady=8, sticky="ew")

        ctk.CTkLabel(
            self.sidebar_frame, text="Chat History:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=2, column=0, padx=20, pady=(10, 0), sticky="w")

        self.history_scroll_frame = ctk.CTkScrollableFrame(
            self.sidebar_frame, fg_color="transparent", height=200
        )
        self.history_scroll_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")
        self.history_scroll_frame.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom.grid(row=4, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkButton(
            bottom, text="💾 Export chat", fg_color="transparent",
            border_width=1, anchor="w", command=self.export_chat,
        ).pack(fill="x", pady=4)
        ctk.CTkButton(
            bottom, text="⚙️ Settings", fg_color="transparent",
            border_width=1, anchor="w", command=self.open_settings_dialog,
        ).pack(fill="x", pady=4)

        self.profile_btn = ctk.CTkButton(
            bottom, text=f"👤 {self.profile_name}",
            fg_color="transparent", border_width=1, anchor="w",
            command=self.open_profile_dialog,
        )
        self.profile_btn.pack(fill="x", pady=4)

    def _build_main_area(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 5))

        self.expand_btn = ctk.CTkButton(
            self.top_bar, text="☰ Menu", width=80, command=self.toggle_sidebar
        )
        self.expand_btn.pack(side="left", padx=5)
        self.expand_btn.pack_forget()

        self.model_selector = ctk.CTkOptionMenu(
            self.top_bar,
            values=list(GEMINI_MODEL_MAP) + list(OPENAI_MODEL_MAP),
            width=160,
        )
        self.model_selector.pack(side="right", padx=5)
        self.model_selector.set("Gemini 2.5 Flash")

        ctk.CTkLabel(
            self.main_frame, text="Where should we start?",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=1, column=0, pady=(20, 20))

        self.chat_display = ctk.CTkTextbox(
            self.main_frame, corner_radius=12, font=ctk.CTkFont(size=14)
        )
        self.chat_display.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.chat_display.configure(state="disabled")

        self.input_frame = ctk.CTkFrame(
            self.main_frame, fg_color="#1E1E2E", corner_radius=25
        )
        self.input_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.prompt_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Ask Project-Kizen...",
            border_width=0,
            fg_color="transparent",
            font=ctk.CTkFont(size=14),
        )
        self.prompt_entry.grid(row=0, column=0, padx=20, pady=12, sticky="ew")
        self.prompt_entry.bind("<Return>", self.send_message)

        self.send_btn = ctk.CTkButton(
            self.input_frame, text="➔", width=40, corner_radius=20,
            command=self.send_message,
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 10), pady=8)

    # ---------------------------------------------------------
    # Cross-thread helpers
    # ---------------------------------------------------------
    def _post_ui(self, callback, *args):
        """Schedule `callback(*args)` on the Tk main thread."""
        self._ui_queue.put((callback, args))

    def _poll_ui_queue(self):
        try:
            while True:
                callback, args = self._ui_queue.get_nowait()
                try:
                    callback(*args)
                except Exception:
                    pass
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(30, self._poll_ui_queue)

    def _append_to_chat(self, text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", text)
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def _on_close(self):
        try:
            self.conn.close()
        finally:
            self.destroy()

    # ---------------------------------------------------------
    # Database
    # ---------------------------------------------------------
    def _init_database(self):
        self.conn = sqlite3.connect("kizen_chats.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        with self._db_lock:
            self.cursor.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "title TEXT, created_at TEXT)"
            )
            self.cursor.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id INTEGER, sender TEXT, message TEXT, "
                "FOREIGN KEY(session_id) REFERENCES sessions(id))"
            )
            self.conn.commit()

    # ---------------------------------------------------------
    # Sidebar / sessions
    # ---------------------------------------------------------
    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar_frame.grid_remove()
            self.expand_btn.pack(side="left", padx=5)
        else:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.expand_btn.pack_forget()
        self.sidebar_visible = not self.sidebar_visible

    def create_new_chat(self):
        if self._is_responding:
            return
        self._create_new_chat_internal()

    def _create_new_chat_internal(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"Chat {timestamp}"
        with self._db_lock:
            self.cursor.execute(
                "INSERT INTO sessions (title, created_at) VALUES (?, ?)",
                (title, timestamp),
            )
            self.conn.commit()
            self.current_session_id = self.cursor.lastrowid
        self.clear_chat_display()
        self.load_sessions_list()

    def load_sessions_list(self):
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        with self._db_lock:
            self.cursor.execute("SELECT id, title FROM sessions ORDER BY id DESC")
            sessions = self.cursor.fetchall()

        for session_id, title in sessions:
            row = ctk.CTkFrame(self.history_scroll_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkButton(
                row, text=title, fg_color="transparent", anchor="w",
                command=lambda sid=session_id: self.load_session(sid),
            ).grid(row=0, column=0, sticky="ew", padx=(0, 2))

            ctk.CTkButton(
                row, text="✏️", width=28, fg_color="transparent",
                hover_color=("#333333", "#222222"),
                command=lambda sid=session_id, t=title: self.open_edit_chat_dialog(sid, t),
            ).grid(row=0, column=1, padx=2)

            ctk.CTkButton(
                row, text="🗑️", width=28, fg_color="transparent",
                hover_color=("#552222", "#441111"),
                command=lambda sid=session_id: self.delete_session(sid),
            ).grid(row=0, column=2, padx=2)

    def load_session(self, session_id):
        if self._is_responding:
            return
        self.current_session_id = session_id
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")

        with self._db_lock:
            self.cursor.execute(
                "SELECT sender, message FROM messages WHERE session_id = ?",
                (session_id,),
            )
            messages = self.cursor.fetchall()

        for sender, msg in messages:
            if sender == "AI":
                self.chat_display.insert("end", f"\n{msg}\n{SEPARATOR}\n")
            else:
                self.chat_display.insert("end", f"\n{sender}: {msg}\n")

        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def open_edit_chat_dialog(self, session_id, current_title):
        EditChatDialog(
            self, current_title,
            lambda new_title: self.rename_session(session_id, new_title),
        )

    def rename_session(self, session_id, new_title):
        with self._db_lock:
            self.cursor.execute(
                "UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id)
            )
            self.conn.commit()
        self.load_sessions_list()

    def delete_session(self, session_id):
        if self._is_responding:
            return
        with self._db_lock:
            self.cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self.conn.commit()

        if self.current_session_id == session_id:
            self._create_new_chat_internal()
        else:
            self.load_sessions_list()

    def save_message_to_db(self, sender, message):
        if not self.current_session_id:
            return
        with self._db_lock:
            self.cursor.execute(
                "INSERT INTO messages (session_id, sender, message) VALUES (?, ?, ?)",
                (self.current_session_id, sender, message),
            )
            self.conn.commit()

    # ---------------------------------------------------------
    # Profile / settings / export
    # ---------------------------------------------------------
    def open_profile_dialog(self):
        ProfileDialog(self, self.profile_name, self.update_profile_name)

    def open_settings_dialog(self):
        SettingsDialog(self, self)

    def update_profile_name(self, new_name):
        self.profile_name = new_name
        self.profile_btn.configure(text=f"👤 {self.profile_name}")

    def export_chat(self):
        content = self.chat_display.get("1.0", "end-1c")
        if not content.strip():
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[
                ("Markdown Files", "*.md"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not export chat:\n{e}")

    # ---------------------------------------------------------
    # Messaging
    # ---------------------------------------------------------
    def send_message(self, event=None):
        if self._is_responding:
            return
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            return

        model = self.model_selector.get()
        self.prompt_entry.delete(0, "end")
        self._append_to_chat(f"\n{self.profile_name}: {prompt}\n")
        self.save_message_to_db(self.profile_name, prompt)

        self._is_responding = True
        self.send_btn.configure(state="disabled")

        threading.Thread(
            target=self._fetch_response, args=(prompt, model), daemon=True
        ).start()

    def _fetch_response(self, prompt, model):
        """Worker-thread: stream chunks and marshal UI updates to main thread."""
        self._post_ui(self._append_to_chat, f"\n{model}: ")
        response_text = ""
        try:
            for chunk in self._stream_response(prompt, model):
                response_text += chunk
                self._post_ui(self._append_to_chat, chunk)
        except Exception as e:
            err = f"[Error Occurred]: {e}"
            response_text += err
            self._post_ui(self._append_to_chat, err)
        finally:
            self._post_ui(self._append_to_chat, f"\n{SEPARATOR}\n")
            self.save_message_to_db("AI", f"{model}: {response_text}")
            self._post_ui(self._on_response_finished)

    def _on_response_finished(self):
        self._is_responding = False
        self.send_btn.configure(state="normal")

    def _stream_response(self, prompt, model):
        """Generator yielding text chunks for the selected model."""
        if model in GEMINI_MODEL_MAP:
            if self.GEMINI_API_KEY.startswith("ENTER_"):
                raise RuntimeError(
                    "Gemini API key is not set. Open Settings to configure it."
                )
            client = genai.Client(api_key=self.GEMINI_API_KEY)
            for chunk in client.models.generate_content_stream(
                model=GEMINI_MODEL_MAP[model], contents=prompt
            ):
                if chunk.text:
                    yield chunk.text
        elif model in OPENAI_MODEL_MAP:
            if self.OPENAI_API_KEY.startswith("ENTER_"):
                raise RuntimeError(
                    "OpenAI API key is not set. Open Settings to configure it."
                )
            client = OpenAI(api_key=self.OPENAI_API_KEY)
            stream = client.chat.completions.create(
                model=OPENAI_MODEL_MAP[model],
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        else:
            raise ValueError(f"Unknown model: {model}")

    def clear_chat_display(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")


if __name__ == "__main__":
    app = ProjectKizenClient()
    app.mainloop()
