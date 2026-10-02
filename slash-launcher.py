#!/usr/bin/env python3
import json
import logging
import os
import select
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

from evdev import InputDevice, UInput, ecodes, list_devices
from PySide6.QtCore import Qt, Signal, QObject, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

BASE = Path(__file__).resolve().parent
COMMANDS_FILE = BASE / "commands.json"
LOG_FILE = Path.home() / ".local/state/kubuntu-slash-commands/launcher.log"
DOUBLE_SLASH_SECONDS = 0.280
SLASH_CODES = {ecodes.KEY_SLASH, getattr(ecodes, "KEY_KPSLASH", 98)}

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("kubuntu-slash-commands")


class Bus(QObject):
    trigger = Signal()
    resume = Signal()


class Palette(QDialog):
    def __init__(self, commands, bus):
        super().__init__()
        self.commands = commands
        self.bus = bus

        self.setWindowTitle("Slash Commands")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(560, 82)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Type a command…")
        self.edit.returnPressed.connect(self.execute)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.edit)

        self.setStyleSheet("""
            QDialog {
                background: rgba(7, 26, 28, 248);
                border: 1px solid rgba(80, 227, 212, 90);
                border-radius: 14px;
            }
            QLineEdit {
                background: rgba(10, 37, 39, 235);
                border: 1px solid rgba(80, 227, 212, 55);
                border-radius: 9px;
                padding: 11px 13px;
                color: #d9fffa;
                font-size: 16px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(80, 227, 212, 120);
            }
        """)

    def show_palette(self):
        log.info("Opening command palette")
        self.edit.clear()
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus(Qt.OtherFocusReason)

    def execute(self):
        text = self.edit.text().strip()
        self.hide()
        self.bus.resume.emit()

        if not text:
            return

        parts = text.split(maxsplit=1)
        command = parts[0].lstrip("/").lower()
        query = parts[1] if len(parts) == 2 else ""

        data = self.commands.get(command)
        if not data:
            log.warning("Unknown command: /%s", command)
            return

        url = data["url"].replace("{query}", quote(query, safe=""))
        log.info("Running /%s", command)
        QDesktopServices.openUrl(QUrl(url))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.bus.resume.emit()
            return
        super().keyPressEvent(event)


class KeyboardBridge:
    def __init__(self, bus):
        self.bus = bus
        self.stop = threading.Event()
        self.active = False
        self.devices = []
        self.uinput = None
        self.pending = []
        self.pending_since = 0.0
        self.lock = threading.Lock()
        self.swallow_release = False

    def start(self):
        keyboards = []
        for path in list_devices():
            try:
                dev = InputDevice(path)
                caps = dev.capabilities().get(ecodes.EV_KEY, [])
                keys = {x[0] if isinstance(x, tuple) else x for x in caps}
                if SLASH_CODES & keys and any(k < ecodes.BTN_MISC for k in keys):
                    keyboards.append(dev)
                else:
                    dev.close()
            except Exception as exc:
                log.debug("Ignoring input device %s: %s", path, exc)

        if not keyboards:
            raise RuntimeError(
                "No accessible keyboard devices found. "
                "Check input-group membership and /dev/input permissions."
            )

        self.uinput = UInput(
            {ecodes.EV_KEY: list(range(1, 768))},
            name="Kubuntu Slash Commands Virtual Keyboard",
        )

        for dev in keyboards:
            dev.grab()
            self.devices.append(dev)
            log.info("Grabbed keyboard: %s (%s)", dev.name, dev.path)

        log.info("Monitoring %d keyboard(s); slash codes=%s", len(self.devices), sorted(SLASH_CODES))
        threading.Thread(target=self.read_loop, daemon=True, name="keyboard-monitor").start()

    def emit(self, event):
        if not self.uinput:
            return
        if event.type == ecodes.EV_KEY:
            self.uinput.write_event(event)
            self.uinput.syn()
        elif event.type == ecodes.EV_SYN:
            self.uinput.syn()

    def flush_pending(self):
        for event in self.pending:
            self.emit(event)
        self.pending.clear()
        self.pending_since = 0.0

    def read_loop(self):
        fd_map = {dev.fd: dev for dev in self.devices}
        while not self.stop.is_set():
            try:
                ready, _, _ = select.select(list(fd_map), [], [], 0.5)
            except (OSError, ValueError):
                log.exception("Keyboard select failed")
                break

            with self.lock:
                if (
                    not self.active
                    and self.pending
                    and time.monotonic() - self.pending_since > DOUBLE_SLASH_SECONDS
                ):
                    self.flush_pending()

            for fd in ready:
                dev = fd_map.get(fd)
                if not dev:
                    continue
                try:
                    events = dev.read()
                except Exception:
                    log.exception("Keyboard read failed for %s", dev.path)
                    continue
                for event in events:
                    self.handle_event(event)

    def handle_event(self, event):
        with self.lock:
            if self.stop.is_set():
                return

            if self.active:
                if (
                    self.swallow_release
                    and event.type == ecodes.EV_KEY
                    and event.code in SLASH_CODES
                    and event.value == 0
                ):
                    self.swallow_release = False
                    return
                self.emit(event)
                return

            now = time.monotonic()
            is_slash = event.type == ecodes.EV_KEY and event.code in SLASH_CODES

            if is_slash and event.value == 1:
                if self.pending and now - self.pending_since <= DOUBLE_SLASH_SECONDS:
                    self.pending.clear()
                    self.pending_since = 0.0
                    self.active = True
                    self.swallow_release = True
                    log.info("Detected //")
                    self.bus.trigger.emit()
                else:
                    if self.pending:
                        self.flush_pending()
                    self.pending = [event]
                    self.pending_since = now
                return

            if self.pending:
                self.pending.append(event)
                return

            self.emit(event)

    def resume(self):
        with self.lock:
            self.active = False
            self.swallow_release = False
            self.pending.clear()
            self.pending_since = 0.0
        log.info("Keyboard forwarding resumed")

    def shutdown(self):
        self.stop.set()
        with self.lock:
            self.flush_pending()
        for dev in self.devices:
            try:
                dev.ungrab()
                dev.close()
            except Exception:
                pass
        if self.uinput:
            self.uinput.close()
        log.info("Keyboard bridge stopped")


def load_commands():
    with open(COMMANDS_FILE, encoding="utf-8") as f:
        return json.load(f)


def main():
    log.info("Starting Kubuntu Slash Commands (PID %s)", os.getpid())
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bus = Bus()
    palette = Palette(load_commands(), bus)
    bridge = KeyboardBridge(bus)
    bus.trigger.connect(palette.show_palette)
    bus.resume.connect(bridge.resume)
    app.aboutToQuit.connect(bridge.shutdown)

    try:
        bridge.start()
    except Exception:
        log.exception("Startup failed")
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
