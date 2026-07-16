from __future__ import annotations

import queue
import shutil
import sys
import threading
import time
from datetime import datetime

from pynput import keyboard
from PyQt6.QtWidgets import QApplication

from ai.claude import ClaudeBackend
from ai.openai_client import OpenAIBackend
from audio.capture import AudioCapture
from audio.transcriber import Transcriber
from config import Config
from db import ConversationDB
from screen.capture import capture_screen
from ui.overlay import Overlay, OverlaySignals

DEBOUNCE_SECONDS     = 2.5
MAX_PENDING_SEGMENTS = 5
HOTKEY               = "<cmd>+<shift>+s"
RAISE_HOTKEY         = "<cmd>+<shift>+o"
MUTE_HOTKEY          = "<cmd>+<shift>+a"


def main():
    config = Config()
    db     = ConversationDB()

    # ── Backends ───────────────────────────────────────────────────────────────
    backends:  dict      = {}
    available: list[str] = []

    if config.anthropic_api_key:
        backends["claude"] = ClaudeBackend(config.anthropic_api_key)
        available.append("claude")
        print("[main] Claude backend ready.")

    if config.openai_api_key:
        backends["openai"] = OpenAIBackend(config.openai_api_key)
        available.append("openai")
        print("[main] OpenAI backend ready.")

    if shutil.which("claude"):
        from ai.claude_code import ClaudeCodeBackend
        backends["claude_code"] = ClaudeCodeBackend(config.project_dir)
        available.append("claude_code")
        print(f"[main] Claude Code backend ready. Project dir: {config.project_dir}")
    else:
        print("[main] Claude Code CLI not found — skipping that backend.")

    if not backends:
        print("ERROR: No backends available. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
              "or install Claude Code CLI.")
        sys.exit(1)

    current_backend: dict = {"name": available[0]}

    # ── Session state ──────────────────────────────────────────────────────────
    session_id: dict = {"value": db.start_session()}

    # ── Queues & shared state ──────────────────────────────────────────────────
    audio_queue:      queue.Queue = queue.Queue()
    transcript_queue: queue.Queue = queue.Queue()
    hotkey_triggered: dict        = {"value": False}
    paused:           dict        = {"value": False}

    # ── Audio pipeline ─────────────────────────────────────────────────────────
    capture     = AudioCapture(audio_queue, config.audio_device_name)
    transcriber = Transcriber(
        audio_queue, transcript_queue,
        config.whisper_model, config.silence_rms_threshold,
    )

    # ── Qt app + overlay ───────────────────────────────────────────────────────
    app = QApplication(sys.argv)

    # Hide from Dock / Cmd+Tab — the overlay uses a plain NSWindow (not NSPanel)
    # so it would otherwise appear there as a regular app.
    if sys.platform == "darwin":
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

    signals = OverlaySignals()
    overlay = Overlay(signals, available)
    overlay.show()

    ts = datetime.now().strftime("%b %d, %Y  %H:%M")
    overlay.set_session_label(f"SESSION STARTED  {ts}")

    def _new_session():
        db.end_session(session_id["value"])
        session_id["value"] = db.start_session()
        ts = datetime.now().strftime("%b %d, %Y  %H:%M")
        overlay.set_session_label(f"SESSION STARTED  {ts}")
        print(f"[session] New session #{session_id['value']}")

    signals.switch_backend.connect(lambda b: current_backend.update({"name": b}))
    signals.end_session.connect(_new_session)

    # ── Hotkeys ────────────────────────────────────────────────────────────────
    def on_hotkey():
        hotkey_triggered["value"] = True

    def on_mute_hotkey():
        paused["value"] = not paused["value"]
        if paused["value"]:
            capture.stop()
            signals.set_status.emit("🔇 Muted")
        else:
            capture.start()
            signals.set_status.emit("🎙 Listening")

    def on_raise_hotkey():
        signals.raise_overlay.emit()

    hotkey_listener = keyboard.GlobalHotKeys({
        HOTKEY:       on_hotkey,
        MUTE_HOTKEY:  on_mute_hotkey,
        RAISE_HOTKEY: on_raise_hotkey,
    })
    hotkey_listener.start()
    print(f"[main] Hotkeys: {HOTKEY} = capture  |  {MUTE_HOTKEY} = mute/unmute  |  {RAISE_HOTKEY} = show overlay")

    # ── AI worker ──────────────────────────────────────────────────────────────
    full_transcript: list[str] = []

    def query_ai(display_text: str, ai_context: str):
        screenshot_b64 = None
        try:
            signals.set_status.emit("📸 Capturing screen…")
            screenshot_b64 = capture_screen()
            if not screenshot_b64:
                print("[screen] Warning: capture returned empty")
        except Exception as exc:
            print(f"[screen] Capture failed: {exc}")
            signals.set_status.emit("⚠ Screen capture failed")

        # Show only the new speech in the conversation log.
        db.add_message(session_id["value"], "user", display_text)
        signals.add_user_turn.emit(display_text)

        try:
            backend  = backends[current_backend["name"]]
            # Send full rolling context to the AI for better answers.
            response = backend.get_response(ai_context, screenshot_b64)
            db.add_message(session_id["value"], "ai", response)
            signals.add_ai_turn.emit(response)
            signals.set_status.emit("✓ Done")
        except Exception as exc:
            err = f"[Error] {exc}"
            db.add_message(session_id["value"], "ai", err)
            signals.add_ai_turn.emit(err)
            signals.set_status.emit("")

    def ai_worker():
        pending:       list[str]    = []
        last_received: float | None = None

        while True:
            try:
                text = transcript_queue.get(timeout=0.2)
                pending.append(text)
                full_transcript.append(text)
                last_received = time.time()
            except queue.Empty:
                pass

            forced    = hotkey_triggered["value"]
            elapsed   = (time.time() - last_received) if last_received else 0
            debounced = pending and elapsed >= DEBOUNCE_SECONDS
            maxed     = pending and len(pending) >= MAX_PENDING_SEGMENTS

            if not (forced or debounced or maxed):
                continue

            hotkey_triggered["value"] = False
            display_text = " ".join(pending)             # only new words → shown in "Me:"
            ai_context   = " ".join(full_transcript[-10:])  # full rolling context → sent to AI
            pending.clear()
            last_received = None

            threading.Thread(
                target=query_ai, args=(display_text, ai_context), daemon=True
            ).start()

    ai_thread = threading.Thread(target=ai_worker, daemon=True)

    # ── Start ──────────────────────────────────────────────────────────────────
    capture.start()
    transcriber.start()
    ai_thread.start()

    print(f"[main] Session #{session_id['value']} started.")
    exit_code = app.exec()

    db.end_session(session_id["value"])
    db.close()
    if not paused["value"]:
        capture.stop()
    transcriber.stop()
    hotkey_listener.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
