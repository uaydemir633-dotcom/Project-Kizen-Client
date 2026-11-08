<div align="center">

# ⚡ Project-Kizen

### Multi-provider AI desktop client in a single Python file

**Gemini · OpenAI · OpenRouter · Groq · any OpenAI-compatible endpoint (Ollama, LM Studio, LiteLLM, vLLM)**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-1.3.0-blue?style=flat-square)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](#-license)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square)]()
[![UI](https://img.shields.io/badge/UI-PySide6%20%7C%20CustomTkinter-41CD52?style=flat-square&logo=qt&logoColor=white)]()

</div>

---

## 🌟 Overview

**Project-Kizen** is a Gemini-inspired desktop AI client that lets you chat with multiple
providers from one unified interface. Bring your own API keys and switch between cloud
models (Gemini 2.5, GPT-4o, Claude 3.5 via OpenRouter, Llama 3.3 via Groq) or any local
OpenAI-compatible endpoint — with real-time streaming, persistent chat history, and a
distraction-free UI.

The project ships in **two parallel UI eras**, both fully functional and both single-file:

| Era | Framework | Latest | Status |
|---|---|---|---|
| **Classic** | CustomTkinter (Tk) | `v1.2.0b1` | ✅ Stable |
| **Next-gen** | PySide6 (Qt 6) | `v1.3.0` | ✅ Stable (recommended) |

Both share the same **backend, providers, config format, and SQLite database**, so you
can switch between them without losing data.

---

## 🚀 Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/Project-Kizen-Client.git
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
- **Live markdown rendering** (PySide6 only) — headings, lists, quotes, inline code,
  links, bold/italic, and fenced code blocks render *as the model types*
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
- **Code block rendering** — fenced blocks get a monospace font and a distinct background;
  PySide6 additionally shows a language label and a per-block copy button

### 🎨 Interface

- **Gemini-inspired dark/light theme** with instant preview
- **6 accent colours** — send button updates live; the rest applies after restart
- **Collapsible sidebar** — expanded (with titles) ↔ collapsed (icon rail)
- **Adjustable chat font size** (11–20 px) with a live preview in Settings
- **DPI-aware dialogs** (PySide6) — modals auto-centre and shrink to fit small screens
- **Toast notifications** and **tooltips**

### ⚙️ Configuration

Everything persists to `~/.kizen_config.json` (atomic writes via `os.replace`, `chmod 600`
on Unix):

| Group | Options |
|---|---|
| **Profile** | Display name (cannot be `"AI"`) |
| **Defaults** | Default model |
| **Behaviour** | Enter-to-send, auto-scroll, confirm-on-close |
| **Chat** | System prompt (6 presets), Temperature (0–2), Top-P (0–1), Max Tokens (0 = provider default, up to 1,000,000), History Limit (1–500) |
| **Appearance** | Theme (Dark/Light/System), accent colour, chat font size (11–20) |
| **API Keys** | OpenAI, Gemini, OpenRouter, Groq + custom endpoints |

### 💾 Data & portability

- **SQLite persistence** at `~/.kizen/kizen_chats.db` (WAL mode, indexed)
- **Export chats** → JSON (full backup) or Markdown (human-readable)
- **Import chats** → JSON with duplicate detection
- **Export / import settings** → JSON, with an optional "include API keys" checkbox
- **Reset to defaults** → keeps API keys and custom models
- **Storage stats** — chat count, message count, and DB size, computed on demand

---

## 🆚 Which UI should I use?

Both share the same backend, providers, and storage format — the difference is the UI
toolkit and platform integration.

| Feature | CustomTkinter (`v1.2.0b1`) | PySide6 (`v1.3.0`) |
|---|:---:|:---:|
| Multi-provider streaming | ✅ | ✅ |
| Live markdown rendering | ⚠️ fenced code blocks only | ✅ headings, lists, quotes, inline code, links, bold/italic |
| Native OS dialogs (`QFileDialog`, `QMessageBox`) | ❌ (Tk) | ✅ |
| DPI / HiDPI scaling | ⚠️ partial | ✅ native |
| Live theme switching | ⚠️ partial | ✅ full |
| Approx. RAM usage | ~90 MB | ~140 MB |
| Install footprint | small | larger (`PySide6`) |

**Recommendation:** `v1.3.0` (PySide6) for new users and high-DPI screens.
`v1.2.0b1` (CustomTkinter) if you want minimal dependencies.

---

## 🧩 Adding custom models

Any OpenAI-compatible server works out of the box.
Go to **Settings → API Keys → Custom Models → ＋ Add Custom Model**:

| Field | Example |
|---|---|
| Display Name | `Local Llama` |
| Base URL | `http://localhost:11434/v1` *(Ollama)* |
| API Key | *(leave empty for local servers)* |
| Model ID | `llama3.2` |

Common setups:

```text
# Ollama
http://localhost:11434/v1        → llama3.2, qwen2.5, mistral

# LM Studio
http://localhost:1234/v1         → (your loaded model)

# LiteLLM
http://localhost:4000/v1         → (any proxy-routed model)

# vLLM
http://localhost:8000/v1         → (served model id)
```

The custom model appears instantly in every model selector.

---

## ⌨️ Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + N` | New chat |
| `Ctrl + ,` | Open settings |
| `Escape` | Stop the current response |
| `Shift + Enter` | Newline (never sends) |
| `Ctrl + Enter` | Force send (works even when Enter-to-send is off) |
| `↑` *(in empty input)* | Recall the last prompt |
| `Ctrl + S` *(inside Settings dialog)* | Save |

---

## 📥 Installation

### Prerequisites

- **Python 3.10+** (tested on 3.11 and 3.12)
- A terminal that supports UTF-8 (for emoji rendering)

### Which file should I run?

| File | UI | Status | Recommended for |
|---|---|---|---|
| `project_kizen_client_v1_3_0.py` | PySide6 | ✅ Stable | New users, high-DPI screens, native feel |
| `project_kizen_client_v1_2_0b1.py` | CustomTkinter | ✅ Latest CTk | Minimal dependencies |
| `project_kizen_client_v1_2_0.py` | CustomTkinter | ✅ Stable | Pre-hotfix baseline |
| `project_kizen_client_v1_1_0b1.py` | CustomTkinter | ✅ Stable | Legacy |
| `project_kizen_client_v1_1_0.py` | CustomTkinter | ✅ Stable | Legacy |
| `project_kizen_client_v1_0_0a1.py` | CustomTkinter | ⚠️ Alpha | Historical reference only |

### Install — PySide6 (recommended)

```bash
git clone https://github.com/YOUR_USERNAME/Project-Kizen-Client.git
cd Project-Kizen-Client

pip install PySide6 openai google-genai

python project_kizen_client_v1_3_0.py
```

### Install — CustomTkinter (minimal dependencies)

```bash
git clone https://github.com/YOUR_USERNAME/Project-Kizen-Client.git
cd Project-Kizen-Client

pip install customtkinter openai google-genai

python project_kizen_client_v1_2_0b1.py
```

### First-time setup

1. Launch the app — a config file is created at `~/.kizen_config.json`
2. Click **⚙️** in the sidebar (or press `Ctrl + ,`)
3. Open the **API Keys** tab
4. Paste any combination of keys:
   - **OpenAI** — https://platform.openai.com/api-keys
   - **Gemini** — https://aistudio.google.com/app/apikey
   - **OpenRouter** — https://openrouter.ai/keys
   - **Groq** — https://console.groq.com/keys
5. Click **Test** to verify connectivity (with per-provider latency)
6. Click **Save**

You only need **one** provider to start using the app.

---

## 🗂️ Version history

### `v1.3.0` — PySide6 stable
- 🔁 **Complete UI rewrite** from CustomTkinter to **PySide6 (Qt 6)**
- Native QSS theming and `QStackedWidget` for welcome ↔ chat transitions
- `Signal/Slot`-based cross-thread marshalling (replaces the manual queue + polling loop)
- `QTimer`-driven autoscroll; `QShortcut` for keyboard bindings
- Native `QFileDialog` and `QMessageBox`
- **Live markdown rendering** — fenced code blocks *and* inline formatting during streaming
- Graceful import-time fallbacks if `google-genai` or `openai` isn't installed
- Per-message role coalescing when building provider history
- Defensive error handling around Gemini's `chunk.text`

### `v1.2.0b1` — Performance & stability (CustomTkinter, latest in the CTk branch)
- Streaming hot-path optimisations (buffered flushing, chunk counter, no `cget()` per chunk)
- History sanitiser strips inline error/stop markers before sending context
- Thread-safe DB writes with `_db_lock`
- Atomic config writes (`os.replace` + `chmod 600`)
- Session cap (500) keeps the sidebar responsive on large DBs
- WAL mode + indexes on `messages(session_id, id)` and `sessions(id DESC)`
- Stream resources explicitly closed on stop

### `v1.2.0` — Multi-tab Settings & theming
- Multi-tab Settings dialog (General / Chat / Appearance / API Keys / Data / About)
- System prompt presets, Temperature, Top-P, Max Tokens, History Limit
- Dark/Light/System + 6 accent colours + adjustable chat font size
- DPI-aware dialogs (`_center_on`, `_make_modal`)
- JSON & Markdown chat export / import
- Settings export / import with optional API-key exclusion
- Storage stats, prompt history, code-block rendering
- WCAG-oriented light palette

### `v1.1.0b1` — Auto-titling & polish
- Auto-titling from the first user message
- Empty-session pruning
- Inline error messages excluded from stored history
- DB path moved to `~/.kizen/kizen_chats.db` (see **Known limitations**)

### `v1.1.0` — Gemini-inspired redesign
- Expanded / collapsed sidebar layout
- Per-message model tracking
- OpenRouter + Groq integration
- Custom model manager (basic)
- `MessageBubble` widget with copy button

### `v1.0.0a1` — Initial alpha
- Basic GUI for Gemini + OpenAI
- Streaming responses
- SQLite persistence
- Chat CRUD + Markdown export

---

## 📁 Project structure

```text
Project-Kizen-Client/
├── project_kizen_client_v1_3_0.py        # PySide6, stable (recommended)
├── project_kizen_client_v1_3_0b1.py      # PySide6, beta (older draft of v1.3.0)
├── project_kizen_client_v1_2_0b1.py      # CustomTkinter, latest stable
├── project_kizen_client_v1_2_0.py        # CustomTkinter, stable
├── project_kizen_client_v1_1_0b1.py      # CustomTkinter, stable
├── project_kizen_client_v1_1_0.py        # CustomTkinter, legacy
├── project_kizen_client_v1_0_0a1.py      # CustomTkinter, alpha (historical)
├── README.md
├── LICENSE                               # MIT
└── docs/
    └── screenshots/                      # (optional)
```

Runtime files (auto-created, not in the repo):

```text
~/.kizen_config.json                    # User settings + API keys (chmod 600)
~/.kizen/kizen_chats.db                 # SQLite database (WAL mode)
~/.kizen/kizen_chats.db-wal             # SQLite WAL
~/.kizen/kizen_chats.db-shm             # SQLite shared memory
```

---

## 🏗️ Technical notes

A few behaviours that matter if you're reading or forking the source:

- **Streaming frequency.** Both UIs flush streamed chunks to the screen every
  `FLUSH_INTERVAL = 0.05` seconds (20 Hz). This is deliberate — high enough to feel
  real-time, low enough to keep the UI thread responsive with long responses.
- **History window is message-based, not token-based.** `history_limit` (1–500)
  counts *messages* (user + assistant), not tokens. Long messages can still hit a
  provider's context limit. Lower the limit in **Settings → Chat** if you see 4k
  or context errors.
- **Role coalescing (PySide6 only).** Consecutive same-role messages are merged
  with `\n\n` before being sent to a provider, because some APIs reject adjacent
  identical roles. The CustomTkinter branch sends them as-is.
- **Empty sessions are pruned on the fly.** Creating a new chat deletes the
  previous session if it has zero messages, so the sidebar doesn't fill with
  empty "New Chat" rows.
- **Missing provider libraries are non-fatal in PySide6.** If `google-genai` or
  `openai` isn't installed, the app still launches; the specific provider raises
  a clear error only when you try to use it. The CustomTkinter branch imports
  them at module top level and will fail to start if they're missing.
- **API keys are cleaned on read.** Whitespace, zero-width characters, and
  surrounding quotes are stripped, and any value starting with `ENTER_` is treated
  as "not set".

---

## 🛣️ Roadmap

### ✅ Shipped
- [x] **v1.0.0a1** — Initial GUI, Gemini + OpenAI, streaming, SQLite, chat CRUD, Markdown export
- [x] **v1.1.0** — Gemini-inspired redesign, expanded/collapsed sidebar, per-message model, OpenRouter + Groq, custom models
- [x] **v1.1.0b1** — Auto-titling, empty-session pruning, error messages excluded from history
- [x] **v1.2.0** — Multi-tab Settings, system prompt presets, Temperature/Top-P/Max-Tokens, theme + accent picker, chat font size, DPI-aware dialogs, JSON/Markdown chat export & import, settings export/import, storage stats, prompt history, code-block rendering, WCAG-oriented light mode
- [x] **v1.2.0b1** — Streaming hot-path optimisations, history sanitiser, thread-safe DB, atomic config writes
- [x] **v1.3.0** — Full PySide6 migration (Qt 6, Signal/Slot threading, native dialogs, native DPI, live markdown streaming)

### 🚧 In progress / planned

#### v1.3.1 — PySide6 polish
- [ ] Close the CustomTkinter feature-parity gap (message regeneration, per-message actions)
- [ ] Native Qt syntax highlighting (`QSyntaxHighlighter` + Pygments)
- [ ] Resolve remaining DPI and font-rendering issues on Linux/Wayland
- [ ] Optional: standalone binary (PyInstaller / Nuitka)

#### v1.4.0 — "Polish"
- [ ] In-app screenshot / theme preview in Settings
- [ ] Per-message regeneration button (`🔄` next to copy)
- [ ] Token counter (using `tiktoken` where applicable)
- [ ] Search / filter chats in the sidebar
- [ ] Pin / favourite sessions

#### v1.5.0 — "Multimodal"
- [ ] Image & file attachments (Gemini 2.5 vision, GPT-4o vision)
- [ ] Drag-and-drop file support
- [ ] Persistent attachment thumbnails in message bubbles

#### v2.0.0 — "Power User"
- [ ] Full Markdown + syntax highlighting (Pygments) in both UIs
- [ ] Text-to-speech playback for AI messages
- [ ] Conversation branching / edit-and-resend
- [ ] Provider failover (retry on error with an alternate model)
- [ ] Encrypted API-key storage via the OS keychain (`keyring`)

---

## 🐛 Known limitations

- **API keys are stored as plain text** in `~/.kizen_config.json`. The file is
  `chmod 600` on Unix, but Windows ACLs are not tightened. Encrypted storage via
  `keyring` is on the v2.0 roadmap.
- **`history_limit` counts messages, not tokens.** Very long messages can still
  hit a provider's context limit — lower the limit in **Settings → Chat** if you
  see context errors.
- **No automatic retry on network errors.** An error message is shown inline and
  excluded from history; resend manually.
- **Code blocks are rendered as plain monospace text** — no syntax highlighting yet
  (planned for v1.3.1).
- **Database path changed between `v1.1.0b1` and `v1.2.0`.** `v1.1.0b1` stored
  `kizen_chats.db` in the current working directory; `v1.2.0+` uses
  `~/.kizen/kizen_chats.db`. There is **no automatic migration** — if you are
  upgrading from `v1.1.0b1`, copy your existing `kizen_chats.db` to
  `~/.kizen/kizen_chats.db` (create the directory first) or your chat list will
  appear empty.
- **PySide6 UI is new.** If you hit a rendering glitch or DPI scaling issue, please
  open an issue. The CustomTkinter version (`v1.2.0b1`) remains fully supported.

---

## ❓ FAQ

**Q: Do I need all four API keys?**
No. One provider is enough. The app will refuse to call a provider whose key is
missing or still starts with `ENTER_` and show a clear error.

**Q: Can I use a local model without any cloud key?**
Yes. Any OpenAI-compatible server (Ollama, LM Studio, LiteLLM, vLLM, …) works as a
**custom model** — see [Adding custom models](#-adding-custom-models). Leave the API
key empty for local servers.

**Q: Where is my chat history stored?**
SQLite at `~/.kizen/kizen_chats.db`. Both UIs read the same file.

**Q: Can I use both UIs at the same time?**
You can launch both, but SQLite WAL mode allows concurrent readers with a single
writer; two writers can collide. For safety, close one before sending in the other.

**Q: How do I reset everything?**
Delete `~/.kizen_config.json` and `~/.kizen/kizen_chats.db` (plus the `-wal`/`-shm`
siblings). Settings → Data → **Delete all chats** only removes the chats, not the
config.

---

## 🤝 Contributing

Issues and pull requests are welcome. A few guidelines:

1. **Bug reports** — include your Python version, OS, which UI (CustomTkinter vs
   PySide6), and the full traceback from the terminal.
2. **Feature requests** — check the roadmap first; open a discussion before a big PR.
3. **Code style** — the "one file, everything visible" structure is intentional;
   keep it unless you're proposing a broader refactor.
4. **Testing** — smoke-test on at least one provider before submitting.
5. **UI parity** — when fixing a bug in one UI, mention whether the other
   (CustomTkinter / PySide6) is affected.

---

## 🙏 Acknowledgments

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) by Tom Schimansky — the original UI framework
- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) — the next-gen UI framework
- [google-genai](https://github.com/googleapis/python-genai) — Gemini SDK
- [openai-python](https://github.com/openai/openai-python) — OpenAI & OpenAI-compatible SDK
- Google Gemini, ChatGPT, and Claude web UIs — visual inspiration

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**Made with ⚡ by Kizen**

*If Project-Kizen saved you from tab-switching, consider giving it a ⭐*

</div>
