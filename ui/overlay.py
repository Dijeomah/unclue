from __future__ import annotations

import sys

from PyQt6.QtCore import QObject, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


# ── macOS window helpers ───────────────────────────────────────────────────────

def _float_above_everything(widget: QWidget) -> None:
    """Make the window appear on all Spaces (including fullscreen) at screensaver
    level. Uses a regular NSWindow (not NSPanel) so CanJoinAllSpaces works."""
    if sys.platform != "darwin":
        return
    import objc
    from AppKit import (
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorStationary,
    )
    from Quartz import CGWindowLevelForKey, kCGScreenSaverWindowLevelKey

    win_id = int(widget.winId())
    if not win_id:
        return
    ns_view   = objc.objc_object(c_void_p=win_id)
    ns_window = ns_view.window()
    if ns_window is None:
        return
    ns_window.setHidesOnDeactivate_(False)
    ns_window.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorFullScreenAuxiliary
        | NSWindowCollectionBehaviorStationary
    )
    ns_window.setLevel_(CGWindowLevelForKey(kCGScreenSaverWindowLevelKey))


def _hide_from_screen_capture(widget: QWidget) -> None:
    """Exclude this window from screen recordings and screen-share apps."""
    if sys.platform != "darwin":
        return
    import objc
    from AppKit import NSWindowSharingNone

    win_id = int(widget.winId())
    if not win_id:
        return
    ns_view   = objc.objc_object(c_void_p=win_id)
    ns_window = ns_view.window()
    if ns_window is None:
        return
    ns_window.setSharingType_(NSWindowSharingNone)


# ── Styles ─────────────────────────────────────────────────────────────────────

_CONTAINER = """
QWidget#container {
    background-color: rgba(75, 75, 82, 0.86);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 18);
}
"""
_HEADER      = "color: rgba(120, 120, 130, 220); font-size: 10px; letter-spacing: 1px;"
_STATUS      = "color: rgba(99, 102, 241, 220); font-size: 10px;"
_HOTKEY      = "color: rgba(100, 100, 115, 180); font-size: 10px;"
_SESSION_HDR = "color: rgba(150,150,165,200); font-size: 9px; letter-spacing: 1px; font-style: italic;"
_DIVIDER     = "color: rgba(255,255,255,12); font-size: 1px;"
_AI_LABEL    = "color: rgba(99, 102, 241, 240); font-size: 11px; font-weight: 700;"
_AI_TEXT     = "color: #f0f0f5; font-size: 13px; line-height: 1.5;"
_USER_LABEL  = "color: rgba(80, 200, 140, 240); font-size: 11px; font-weight: 700;"
_USER_TEXT   = "color: rgba(200, 210, 200, 230); font-size: 12px; line-height: 1.4;"

_BTN_ACTIVE = """
QPushButton {
    background-color: rgba(99, 102, 241, 220);
    color: white; border: none; border-radius: 5px;
    padding: 3px 10px; font-size: 11px; font-weight: 600;
}
"""
_BTN_INACTIVE = """
QPushButton {
    background-color: rgba(50, 50, 58, 200);
    color: rgba(180, 180, 190, 200); border: none;
    border-radius: 5px; padding: 3px 10px; font-size: 11px;
}
QPushButton:hover { background-color: rgba(70, 70, 80, 200); }
QPushButton:disabled { color: rgba(90, 90, 100, 180); }
"""
_BTN_SESSION = """
QPushButton {
    background-color: transparent; color: rgba(230, 80, 80, 200);
    border: 1px solid rgba(230, 80, 80, 100); border-radius: 5px;
    font-size: 11px; padding: 3px 8px;
}
QPushButton:hover { background-color: rgba(230, 80, 80, 40); color: rgba(255, 100, 100, 255); }
"""
_BTN_QUIT = """
QPushButton {
    background-color: transparent; color: rgba(180, 60, 60, 200);
    border: none; font-size: 16px; font-weight: 600; padding: 0px 4px;
}
QPushButton:hover { color: rgba(255, 80, 80, 255); }
"""
_SCROLL_AREA = """
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: transparent; width: 4px; margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,40); border-radius: 2px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


# ── Signals ────────────────────────────────────────────────────────────────────

class OverlaySignals(QObject):
    add_user_turn  = pyqtSignal(str)
    add_ai_turn    = pyqtSignal(str)
    set_status     = pyqtSignal(str)
    switch_backend = pyqtSignal(str)
    raise_overlay  = pyqtSignal()
    end_session    = pyqtSignal()


# ── Conversation turn widget ───────────────────────────────────────────────────

def _make_turn(role: str, text: str) -> QWidget:
    w      = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(2)

    if role == "ai":
        label = QLabel("AI:")
        label.setStyleSheet(_AI_LABEL)
        body  = QLabel(text)
        body.setStyleSheet(_AI_TEXT)
    else:
        label = QLabel("Me:")
        label.setStyleSheet(_USER_LABEL)
        body  = QLabel(text)
        body.setStyleSheet(_USER_TEXT)

    body.setWordWrap(True)
    layout.addWidget(label)
    layout.addWidget(body)
    return w


# ── Overlay widget ─────────────────────────────────────────────────────────────

class Overlay(QWidget):
    def __init__(self, signals: OverlaySignals, available_backends: list[str]):
        super().__init__()
        self._signals        = signals
        self._available      = available_backends
        self._active         = available_backends[0] if available_backends else "claude"
        self._drag_pos       = QPoint()
        self._space_observer = None
        self._build_ui()
        self._connect()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Plain Window (not Tool) so macOS treats it as NSWindow, not NSPanel.
        # NSPanel cannot appear in other apps' fullscreen Spaces even with
        # CanJoinAllSpaces set — NSWindow has no such restriction.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._container = QWidget()
        self._container.setObjectName("container")
        self._container.setFixedWidth(480)
        self._container.setStyleSheet(_CONTAINER)

        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(18, 14, 18, 14)
        inner.setSpacing(8)

        # Header row
        header_row = QHBoxLayout()
        listening  = QLabel("● LISTENING")
        listening.setStyleSheet(_HEADER)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(_STATUS)

        quit_btn = QPushButton("×")
        quit_btn.setStyleSheet(_BTN_QUIT)
        quit_btn.setFixedSize(22, 22)
        quit_btn.setToolTip("Quit")
        quit_btn.clicked.connect(QApplication.instance().quit)

        header_row.addWidget(listening)
        header_row.addStretch()
        header_row.addWidget(self._status_label)
        header_row.addSpacing(8)
        header_row.addWidget(quit_btn)

        # Session timestamp
        self._session_label = QLabel("")
        self._session_label.setStyleSheet(_SESSION_HDR)
        self._session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Divider
        divider = QLabel("─" * 60)
        divider.setStyleSheet(_DIVIDER)

        # Scrollable conversation log
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(_SCROLL_AREA)
        self._scroll.setFixedHeight(320)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._log_widget = QWidget()
        self._log_layout = QVBoxLayout(self._log_widget)
        self._log_layout.setContentsMargins(0, 0, 6, 0)
        self._log_layout.setSpacing(6)
        self._log_layout.addStretch()

        self._scroll.setWidget(self._log_widget)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        self._claude_btn = QPushButton("Claude")
        self._openai_btn = QPushButton("OpenAI")
        self._code_btn   = QPushButton("Code")
        self._claude_btn.clicked.connect(lambda: self._switch("claude"))
        self._openai_btn.clicked.connect(lambda: self._switch("openai"))
        self._code_btn.clicked.connect(lambda: self._switch("claude_code"))
        self._claude_btn.setEnabled("claude" in self._available)
        self._openai_btn.setEnabled("openai" in self._available)
        self._code_btn.setEnabled("claude_code" in self._available)

        end_btn = QPushButton("End Session")
        end_btn.setStyleSheet(_BTN_SESSION)
        end_btn.clicked.connect(self._signals.end_session.emit)

        hotkey_hint = QLabel("⌘⇧S")
        hotkey_hint.setStyleSheet(_HOTKEY)

        bottom.addWidget(self._claude_btn)
        bottom.addWidget(self._openai_btn)
        bottom.addWidget(self._code_btn)
        bottom.addStretch()
        bottom.addWidget(hotkey_hint)
        bottom.addSpacing(8)
        bottom.addWidget(end_btn)

        inner.addLayout(header_row)
        inner.addWidget(self._session_label)
        inner.addWidget(divider)
        inner.addWidget(self._scroll)
        inner.addLayout(bottom)

        outer.addWidget(self._container)
        self._refresh_buttons()
        self.move(60, 60)

    def _connect(self):
        self._signals.add_user_turn.connect(self._on_user_turn)
        self._signals.add_ai_turn.connect(self._on_ai_turn)
        self._signals.set_status.connect(self._on_status)
        self._signals.raise_overlay.connect(self._on_raise)
        self._signals.end_session.connect(self._on_end_session)

    # ── macOS lifecycle ────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        # Defer AppKit calls — the native NSWindow isn't ready at showEvent time.
        QTimer.singleShot(150, self._apply_macos_window_settings)

    def _apply_macos_window_settings(self):
        _float_above_everything(self)
        _hide_from_screen_capture(self)
        self._register_space_observer()

    def _register_space_observer(self):
        """Re-apply window settings on every Space change so the overlay stays
        visible when the user switches to/from fullscreen Spaces."""
        if sys.platform != "darwin" or self._space_observer is not None:
            return
        from AppKit import NSWorkspace

        center = NSWorkspace.sharedWorkspace().notificationCenter()

        def _on_space_change(_notification):
            _float_above_everything(self)

        self._space_observer = center.addObserverForName_object_queue_usingBlock_(
            "NSWorkspaceActiveSpaceDidChangeNotification",
            None,
            None,
            _on_space_change,
        )

    def closeEvent(self, event):
        if sys.platform == "darwin" and self._space_observer is not None:
            from AppKit import NSWorkspace
            NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(
                self._space_observer
            )
        super().closeEvent(event)

    # ── Public ────────────────────────────────────────────────────────────────

    def set_session_label(self, text: str):
        self._session_label.setText(text)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_user_turn(self, text: str):
        self._append_turn("user", text)

    def _on_ai_turn(self, text: str):
        self._append_turn("ai", text)

    def _on_end_session(self):
        while self._log_layout.count() > 1:
            item = self._log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._session_label.setText("")

    def _on_status(self, text: str):
        self._status_label.setText(text)
        if text:
            QTimer.singleShot(3000, lambda: self._status_label.setText(""))

    def _on_raise(self):
        """Pull the overlay onto the currently active Space (e.g. a fullscreen
        browser) without switching Spaces. orderOut_ + orderFrontRegardless()
        detaches the window from its old Space and re-places it on the current
        one; the high window level makes it visible above any fullscreen app."""
        _float_above_everything(self)
        if sys.platform == "darwin":
            import objc
            win_id = int(self.winId())
            if win_id:
                ns_view   = objc.objc_object(c_void_p=win_id)
                ns_window = ns_view.window()
                if ns_window is not None:
                    ns_window.orderOut_(None)
                    ns_window.orderFrontRegardless()
        self.raise_()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _append_turn(self, role: str, text: str):
        stretch_idx = self._log_layout.count() - 1
        self._log_layout.insertWidget(stretch_idx, _make_turn(role, text))
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _switch(self, backend: str):
        if backend not in self._available:
            return
        self._active = backend
        self._refresh_buttons()
        self._signals.switch_backend.emit(backend)

    def _refresh_buttons(self):
        for btn, key in [
            (self._claude_btn, "claude"),
            (self._openai_btn, "openai"),
            (self._code_btn,   "claude_code"),
        ]:
            btn.setStyleSheet(_BTN_ACTIVE if self._active == key else _BTN_INACTIVE)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
