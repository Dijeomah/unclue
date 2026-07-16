# unclue

A real-time AI interview assistant that listens to your microphone, captures your screen, and overlays AI responses — invisibly — on top of any app, including fullscreen browsers.

---

## Features

- **Always-on overlay** — floats above every app, including fullscreen Spaces (e.g. LeetCode in Brave)
- **Screen-capture aware** — sends a screenshot alongside your speech for context-aware answers
- **Invisible to recorders** — hidden from Zoom, Meet, OBS, and any screen-sharing app
- **Persistent session memory** — every conversation is saved to a local SQLite database
- **Multiple AI backends** — Claude, OpenAI, or Claude Code CLI, switchable on the fly
- **Two modes**:
  - `main.py` — live assistant: listens continuously and responds automatically
  - `main_2.py` — interview practice: you speak an answer, mute to trigger a critique

---

## Hotkeys

| Hotkey | Action |
|---|---|
| `⌘⇧S` | Capture screen + trigger AI response |
| `⌘⇧A` | Mute / unmute mic (`main.py`) — fires AI response on mute (`main_2.py`) |
| `⌘⇧O` | Pull overlay onto current Space (use this when in fullscreen) |

---

## Project Structure

```
unclue/
├── main.py                  # Live assistant mode
├── main_2.py                # Interview practice / critique mode
├── main_memory.py           # Standalone prototype (reference)
├── config.py                # Env-based config
├── db.py                    # SQLite session + message store
├── ai/
│   ├── claude.py            # Anthropic Claude backend
│   ├── openai_client.py     # OpenAI backend
│   └── claude_code.py       # Claude Code CLI backend
├── audio/
│   ├── capture.py           # Microphone capture
│   └── transcriber.py       # Whisper transcription
├── screen/
│   └── capture.py           # Screenshot via mss
├── ui/
│   ├── overlay.py           # PyQt6 overlay widget
│   └── ws_server.py         # WebSocket server (extension bridge)
├── extension/               # Browser extension (optional)
│   ├── manifest.json
│   └── content.js
└── conversation_memory.db   # Auto-created SQLite database
```

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url> unclue
cd unclue
python -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # optional

WHISPER_MODEL=base.en           # tiny.en / base.en / small.en
AUDIO_DEVICE_NAME=unclue Aggregate
SILENCE_RMS_THRESHOLD=0.0008
PROJECT_DIR=/path/to/your/project   # for Claude Code backend
```

### 4. macOS permissions (required)

Go to **System Settings → Privacy & Security** and grant:

- **Microphone** — for audio capture
- **Accessibility** — for global hotkeys (`pynput`)
- **Screen Recording** — for screenshot capture (grant to your terminal app)

---

## Running

**Live assistant (responds automatically):**
```bash
python main.py
```

**Interview practice (critique on demand):**
```bash
python main_2.py
```

---

## Session Memory

Every session is stored in `conversation_memory.db`:

- **sessions** table — start/end timestamps per session
- **messages** table — full conversation log with `ai` / `user` roles

Click **End Session** in the overlay to archive the current session and start a fresh one. All past sessions are preserved.

---

## How the Overlay Works

The overlay uses a plain `NSWindow` (not `NSPanel`) at screensaver window level with `NSWindowCollectionBehaviorCanJoinAllSpaces`, which allows it to appear above any app — including fullscreen Spaces — without activating the Python process or switching Spaces. The app is hidden from the Dock and `⌘Tab` switcher via `NSApplicationActivationPolicyAccessory`.
