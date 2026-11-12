<div align="center">

# ⚡Project-Kizen-Client

### Multi-provider AI desktop client in a single Python file

**Gemini · OpenAI · OpenRouter · Groq · any OpenAI-compatible endpoint (Ollama, LM Studio, LiteLLM, vLLM)**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-1.3.0-blue?style=flat-square)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](#-license)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square)]()
[![UI](https://img.shields.io/badge/UI-PySide6%20%7C%20CustomTkinter-41CD52?style=flat-square&logo=qt&logoColor=white)]()

<br>

[![Download for Windows](https://img.shields.io/badge/Download-Windows%20.exe-0078D7?style=for-the-badge&logo=windows)](https://github.com/uaydemir633-dotcom/Project-Kizen-Client/releases/download/v1.3.0/Project-Kizen-Client.exe)
[![View Release Notes](https://img.shields.io/badge/View-Release%20Notes-black?style=for-the-badge&logo=github)](https://github.com/uaydemir633-dotcom/Project-Kizen-Client/releases)

</div>

---

## 🌟 Overview

**Project-Kizen** is a Gemini-inspired desktop AI client that lets you chat with multiple providers from one unified interface. Bring your own API keys and switch between cloud models (Gemini 2.5, GPT-4o, Claude 3.5 via OpenRouter, Llama 3.3 via Groq) or any local OpenAI-compatible endpoint — with real-time streaming, persistent chat history, and a distraction-free UI.

The project ships in **two parallel UI eras**, both fully functional and both single-file:

| Era | Framework | Latest | Status |
|---|---|---|---|
| **Classic** | CustomTkinter (Tk) | `v1.2.0b1` | ✅ Stable (Frozen) |
| **Next-gen** | PySide6 (Qt 6) | `v1.3.0` | ✅ Stable (recommended) |

Both share the same **backend, providers, config format, and SQLite database**, so you can switch between them without losing data.

---

## 🚀 Quick Start

### Option 1: Download Executable (Windows)
You don't need Python installed to use Project-Kizen. Simply download the latest `.exe` from the [Releases page](https://github.com/uaydemir633-dotcom/Project-Kizen-Client/releases/latest) and double-click it to run. 
*(Note: Because the app is newly released and unsigned, Windows SmartScreen might show an "Unknown Publisher" warning. Click "More info" -> "Run anyway").*

### Option 2: Run from Source (Python)
```bash
git clone https://github.com/uaydemir633-dotcom/Project-Kizen-Client.git
cd Project-Kizen-Client

pip install PySide6 openai google-genai

python project_kizen_client_v1_3_0.py
```

Then open **⚙️ → API Keys**, paste at least one provider key, click **Test**, then **Save**.

You only need **one** provider key to start chatting.

---

## ✨ Features

### 🤖 Multi-provider AI

| Provider | Models bundled |
|---|---|
| **Google Gemini** | `gemini-2.5-flash`, `gemini-2.5-pro` |
| **OpenAI** | `gpt-4o-mini`, `gpt-4o` |
| **OpenRouter** | `openrouter/auto`, `anthropic/claude-3.5-sonnet` |
| **Groq** | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant` |
| **Custom (OpenAI-compatible)** | Any `base_url` + `model_id` — Ollama, LM Studio, LiteLLM, vLLM, … |

- **Real-time streaming** — token-by-token rendering with 50 ms buffered flushing
- **Live markdown rendering** (PySide6 only) — headings, lists, quotes, inline code, links, bold/italic, and fenced code blocks render *as the model types*
- **Custom model manager** — add, edit, delete any OpenAI-compatible endpoint from Settings
- **Live connection tester** — validates every configured key with latency readout
- **Multi-turn context** — configurable history window (1–500 messages)

### 💬 Chat experience

- **Session CRUD** — create, load, rename, delete; empty sessions auto-pruned
- **Auto-titling** — the first user message becomes the chat title (truncated to 40 chars)
- **Streaming stop** — interrupt mid-response with `■` or `Escape`
- **Copy-to-clipboard** on every AI message (and per code block in PySide6)
- **Prompt history** — `↑` in an empty input recalls the last prompt; the `＋` menu shows the last 20
- **Multi-line input** — auto-growing textbox (`Shift+Enter` for newlines)
- **Code block rendering** — fenced blocks get a monospace font, distinct background, and a per-block copy button

### 🎨 Interface

- **Gemini-inspired dark/light theme** with instant preview
- **6 accent colours** — send button updates live
- **Collapsible sidebar** — expanded (with titles) ↔ collapsed (icon rail)
- **Adjustable chat font size** (11–20 px) with a live preview in Settings
- **DPI-aware dialogs** (PySide6) — modals auto-centre and shrink to fit small screens
- **Toast notifications** and **tooltips**

### 💾 Data & portability

- **SQLite persistence** at `~/.kizen/kizen_chats.db` (WAL mode, indexed)
- **Export chats** → JSON (full backup) or Markdown (human-readable)
- **Export / import settings** → JSON, with an optional "include API keys" checkbox
- **Storage stats** — chat count, message count, and DB size, computed on demand

---

## 🧪 Performance Benchmark: Kizen vs Official Desktop Apps

A common concern with Python desktop apps is memory footprint. We ran a live comparison on Windows 11 Task Manager to see how **Project-Kizen (PySide6)** stacks up against the **Official Google Gemini Desktop App**.

| Application | RAM Usage (Idle) | Architecture |
|---|:---:|---|
| **Google Gemini (Official)** | **~242 MB** *(6 processes)* | Web-wrapper / Electron-like |
| **Project-Kizen (PySide6)** | **~89 MB** *(2 processes)* | Native Qt 6 + Python |

> **The result:** Project-Kizen uses **less than half the RAM** of the official Gemini desktop app, despite running multi-provider logic, a full SQLite database, and live markdown rendering — all from a **single, zero-install Python file**.

---

## ⌨️ Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + N` | New chat |
| `Ctrl + ,` | Open settings |
| `Escape` | Stop the current response |
| `Shift + Enter` | Newline (never sends) |
| `Ctrl + Enter` | Force send |
| `↑` *(in empty input)* | Recall the last prompt |

---

## 🗂️ Version History

### `v1.3.0` — PySide6 stable
- 🔁 **Complete UI rewrite** from CustomTkinter to **PySide6 (Qt 6)**
- ⚡ `Signal/Slot`-based cross-thread marshalling for rock-solid streaming
- 📝 **Live markdown rendering** — fenced code blocks *and* inline formatting during streaming
- 🪟 Native `QFileDialog` and `QMessageBox` for better OS integration
- 🛡️ Graceful import-time fallbacks if `google-genai` or `openai` isn't installed

*(See previous releases for older CustomTkinter versions)*

---

## 🤝 Contributing

Issues and pull requests are welcome. A few guidelines:
1. **Bug reports** — include your Python version, OS, and which UI you are using.
2. **Code style** — the "one file, everything visible" structure is intentional.

---

## 🙏 Acknowledgments

- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) — the next-gen UI framework
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — the original UI framework
- [google-genai](https://github.com/googleapis/python-genai) — Gemini SDK
- [openai-python](https://github.com/openai/openai-python) — OpenAI & OpenAI-compatible SDK

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Made with ⚡ by Kizen**

*If Project-Kizen saved you from tab-switching, consider giving it a ⭐*

</div>
