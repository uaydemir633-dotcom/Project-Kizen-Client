⚡ Project-Kizen-Client

A high-performance, cross-model AI desktop assistant built with Python and CustomTkinter, designed with a modern dark-mode aesthetic modeled after professional web interfaces (such as Google Gemini and OpenAI ChatGPT).

🌟 Key Features

Cross-Model Support: Seamlessly switch between Google Gemini (gemini-2.5-flash, gemini-2.5-pro) and OpenAI GPT (gpt-4o-mini, gpt-4o) models.

Real-Time Streaming: Streaming responses deliver AI output chunk-by-chunk for zero latency feel.

Collapsible Sidebar (Slim Mode): Responsive side navigation bar toggles between full title view and a compact icon rail.

Full Chat Session Management (CRUD): Create new chat instances, load past sessions, rename chat titles, or delete conversations permanently.

SQLite Persistence: All chat sessions and message histories are securely saved locally in a dual-table SQLite database (kizen_chats.db).

Flexible UI Settings: In-app modal dialogs for switching themes (Dark/Light/System), managing API keys, and editing user profiles.

Chat Export: Easily export any conversation history into clean Markdown (.md) or Text (.txt) files.

🚀 Getting Started

Prerequisites

Python 3.10 or higher installed on your system.

Installation

Clone the repository:

git clone https://github.com/YOUR_USERNAME/Project-Kizen-Client.git
cd Project-Kizen-Client


Install required dependencies:

pip install customtkinter openai google-genai


Run the application:

python project_kizen_client_v1_0.py


⚙️ Configuration

You can configure your API keys directly inside the application:

Open Project-Kizen-Client.

Click on ⚙️ Settings at the bottom of the sidebar.

Input your OpenAI API Key and Gemini API Key.

Click Save & Close.

🛣️ Project Roadmap

Phase 1: v1.0-alpha (Current Status)

[x] Initial release with CustomTkinter GUI.

[x] Integration with OpenAI & Google Gemini APIs.

[x] Live response streaming support.

[x] Local SQLite session & message storage.

[x] Collapsible sidebar navigation.

[x] Session CRUD operations (Create, Read, Update Title, Delete).

[x] Markdown export utility.

Phase 2: v1.1-beta (Next Release)

[ ] Automatic Chat Titling: Automatically generate relevant conversation titles after the first prompt using AI.

[ ] System Prompts / Persona Selector: Custom system instructions to define AI roles (e.g., Code Reviewer, Tutor, Creative Writer).

[ ] Searchable Chat History: Instant search bar in the sidebar to filter past conversations by keyword.

[ ] Enhanced Keyboard Shortcuts: Ctrl+N for new chat, Ctrl+F for search, and optimized Enter/Shift+Enter handling.

Phase 3: v2.0-stable

[ ] Multimodal Attachment Support: File & image upload support for Gemini 2.5 and GPT-4o vision capabilities.

[ ] Rich Text & Code Block Syntax Highlighting: Custom code renderers with one-click copy buttons inside chat messages.

[ ] Local LLM Support (Ollama): Offline execution capability via Ollama endpoint integration.

[ ] Text-to-Speech (TTS): Built-in voice playback for generated AI responses.

📄 License

Distributed under the MIT License. See LICENSE for more information.
