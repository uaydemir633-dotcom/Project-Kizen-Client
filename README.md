<div align="center">

# ⚡ Project-Kizen

### Multi-provider AI desktop client built with Python & CustomTkinter

**Gemini · OpenAI · OpenRouter · Groq · any OpenAI-compatible endpoint (Ollama, LM Studio, LiteLLM, vLLM)**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-1.2.0b1-yellow.svg?style=flat-square)](https://github.com/YOUR_USERNAME/Project-Kizen-Client/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square)]()
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1f6feb?style=flat-square)](https://github.com/TomSchimansky/CustomTkinter)
[![Status](https://img.shields.io/badge/status-beta-orange?style=flat-square)]()

</div>

---

## 🌟 Overview

**Project-Kizen** is a sleek, Gemini-inspired desktop AI client that lets you chat with multiple providers from a single, unified interface. Bring your own API keys and switch between cloud models (Gemini 2.5, GPT-4o, Claude 3.5 via OpenRouter, Llama 3.3 via Groq) or any local OpenAI-compatible endpoint — all with real-time streaming, persistent chat history, and a distraction-free UI.

---

## ✨ Features

### 🤖 Multi-Provider AI

| Provider | Models |
|---|---|
| **Google Gemini** | `gemini-2.5-flash`, `gemini-2.5-pro` |
| **OpenAI** | `gpt-4o-mini`, `gpt-4o` |
| **OpenRouter** | `openrouter/auto`, `anthropic/claude-3.5-sonnet` |
| **Groq** | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant` |
| **Custom (OpenAI-compatible)** | Ollama, LM Studio, LiteLLM, vLLM, any `base_url` + `model_id` |

- **Real-time streaming** — responses render chunk-by-chunk with buffered 20 Hz flushing
- **Custom model manager** — add, edit, and delete any OpenAI-compatible endpoint directly from Settings
- **Live connection tester** — validate every configured API key with latency readout

### 💬 Chat Experience

- **Session CRUD** — create, load, rename, delete; empty sessions are auto-pruned
- **Auto-titling** — first prompt becomes the chat title (truncated to 40 chars)
- **Streaming stop** — interrupt mid-response with `■` button or `Escape`
- **Copy-to-clipboard** on every AI message
- **Prompt history** — `↑` in the input box recalls last prompt; `＋` menu shows last 20
- **Multi-line input** — auto-growing textbox (`Shift+Enter` for newlines)
- **Code block rendering** — inline fenced code with monospace font and background

### 🎨 Interface

- **Gemini-inspired dark/light theme** with instant preview
- **6 accent colors** — send button updates live; rest after restart
- **Collapsible sidebar** — expanded (with titles) ↔ collapsed (icon rail)
- **Adjustable chat font size** (11–20 px) with live preview
- **DPI-aware dialogs** — all modals auto-center and fit smaller screens
- **Toast notifications** for confirmations and errors
- **Tooltips** on every sidebar icon

### ⚙️ Configuration

Everything persists to `~/.kizen_config.json` (atomic writes, `chmod 600`):

| Group | Options |
|---|---|
| **Profile** | Display name |
| **Defaults** | Default model |
| **Behavior** | Enter-to-send toggle, auto-scroll toggle, confirm-on-close toggle |
| **Chat** | System prompt (+ 6 presets), Temperature (0–2), Top-P (0–1), Max Tokens, History Limit (1–500) |
| **Appearance** | Theme (Dark/Light/System), accent color, chat font size |
| **API Keys** | OpenAI, Gemini, OpenRouter, Groq, plus custom endpoints |

### 💾 Data & Portability

- **SQLite persistence** at `~/.kizen/kizen_chats.db` (WAL mode, indexed)
- **Export chats** → JSON (full backup) or Markdown (readable)
- **Import chats** → JSON with duplicate detection
- **Export / import settings** → JSON (with optional API key exclusion)
- **Reset to defaults** → keeps API keys and custom models
- **Storage stats** — chats, messages, and DB size on demand

### ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + N` | New chat |
| `Ctrl + ,` | Open settings |
| `Escape` | Stop current response |
| `Shift + Enter` | Newline (send instead if Enter-send is off) |
| `Ctrl + Enter` | Force send (even when Enter-send is off) |
| `↑` (in empty input) | Recall last prompt |
| `Ctrl + S` (in Settings) | Save |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** (tested on 3.11 and 3.12)
- A terminal that supports UTF-8 (for emoji rendering)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/Project-Kizen-Client.git
cd Project-Kizen-Client
```

Install dependencies:

```bash
pip install customtkinter openai google-genai
```

Run the app:

```bash
python project_kizen_client_v1_2_0b1.py
```

### First-Time Setup

1. Launch the app — a config file is created at `~/.kizen_config.json`
2. Click **⚙️** in the sidebar (or press `Ctrl + ,`)
3. Go to the **API Keys** tab
4. Paste any combination of keys:
   - **OpenAI** — https://platform.openai.com/api-keys
   - **Gemini** — https://aistudio.google.com/app/apikey
   - **OpenRouter** — https://openrouter.ai/keys
   - **Groq** — https://console.groq.com/keys
5. Click **Test** to verify connectivity
6. Click **Save**

You only need **one** provider to start using the app.

---

## 🧩 Adding Custom Models

Any OpenAI-compatible server works out of the box. In **Settings → API Keys → Custom Models → ＋ Add Custom Model**:

| Field | Example |
|---|---|
| Display Name | `Local Llama` |
| Base URL | `http://localhost:11434/v1` *(Ollama)* |
| API Key | *(leave empty for local)* |
| Model ID | `llama3.2` |

Common setups:

```text
# Ollama
http://localhost:11434/v1        → llama3.2, qwen2.5, mistral

# LM Studio
http://localhost:1234/v1         → (your loaded model)

# LiteLLM
http://localhost:4000/v1         → (any proxy-routed model)
```

The custom model appears instantly in every model selector.

---

## 🖥️ Screenshots

> *Coming soon — welcome screen, chat view, settings, custom model dialog.*

*(Drop real screenshots into `docs/screenshots/` and replace this block:)*

```markdown
| Welcome | Chat | Settings |
|---|---|---|
| ![](docs/screenshots/welcome.png) | ![](docs/screenshots/chat.png) | ![](docs/screenshots/settings.png) |
```

---

## 📁 Project Structure

```
Project-Kizen-Client/
├── project_kizen_client_v1_2_0b1.py     # Main application (v1.2.0b1)
├── README.md                             # This file
├── LICENSE                               # MIT
└── docs/
    └── screenshots/                      # (optional)
```

Runtime files (auto-created, not in repo):

```
~/.kizen_config.json                    # User settings + API keys (chmod 600)
~/.kizen/kizen_chats.db                 # SQLite database (WAL mode)
~/.kizen/kizen_chats.db-wal / -shm      # SQLite WAL files
```

---

## 🛣️ Roadmap

### ✅ Shipped

- [x] **v1.0.0a1** — Initial GUI, Gemini + OpenAI, streaming, SQLite, sidebar, chat CRUD, Markdown export
- [x] **v1.1.0** — Gemini-inspired redesign, expanded/collapsed sidebar, per-message model tracking, OpenRouter + Groq integration, custom models (basic)
- [x] **v1.1.0b1** — Auto-titling, empty-session pruning, error messages excluded from history
- [x] **v1.2.0** — Multi-tab Settings, system prompt presets, temperature/Top-P/Max-Tokens, theme + accent picker, chat font size, DPI-aware dialogs, JSON/Markdown chat export & import, settings export/import, storage stats, prompt history, code-block rendering, WCAG-oriented light mode
- [x] **v1.2.0b1** — Streaming hot path optimized (buffered flushing, chunk counter, no cget during streaming), history sanitizer for error messages, thread-safe DB, atomic config writes

### 🚧 In Progress / Planned

#### v1.3.0 — "Polish"
- [ ] In-app screenshot / theme preview in Settings
- [ ] Per-message regeneration button (`🔄` next to copy)
- [ ] Token counter (using `tiktoken` where applicable)
- [ ] Search / filter chats in the sidebar
- [ ] Pin / favorite sessions

#### v1.4.0 — "Multimodal"
- [ ] Image & file attachments (Gemini 2.5 vision, GPT-4o vision)
- [ ] Drag-and-drop file support
- [ ] Persistent attachment thumbnails in message bubbles

#### v2.0.0 — "Power User"
- [ ] Full Markdown + syntax highlighting (Pygments)
- [ ] Text-to-speech playback for AI messages
- [ ] Conversation branching / edit-and-resend
- [ ] Provider failover (retry on error with alternate model)
- [ ] Encrypted API-key storage via OS keychain (`keyring`)

---

## 🐛 Known Limitations

- **API keys are stored as plain text** in `~/.kizen_config.json`. The file is `chmod 600` on Unix, but Windows ACLs are not tightened. Encrypted storage via `keyring` is on the v2.0 roadmap.
- **`history_limit` counts messages, not tokens.** Very long messages can still hit provider context limits — increase safety by lowering the limit in **Settings → Chat**.
- **No retry on network errors.** An error message is shown inline and excluded from history; resend manually.
- **Code blocks are rendered as plain monospace text** — no syntax highlighting yet.

---

## 🤝 Contributing

Issues and pull requests are welcome. A few guidelines:

1. **Bug reports** — include Python version, OS, and the full traceback (from the terminal, not just the toast)
2. **Feature requests** — check the roadmap first; open a discussion before a big PR
3. **Code style** — keep the existing "one file, everything visible" structure unless you're proposing a refactor
4. **Testing** — manual smoke test on at least one provider before submitting

---

## 🙏 Acknowledgments

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) by Tom Schimansky — the UI framework
- [google-genai](https://github.com/googleapis/python-genai) — Gemini SDK
- [openai-python](https://github.com/openai/openai-python) — OpenAI & OpenAI-compatible SDK
- Google Gemini, ChatGPT, and Claude web UIs — for the visual inspiration

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Made with ⚡ by Kizen**

*If Project-Kizen saved you from tab-switching, consider giving it a ⭐*

</div>
