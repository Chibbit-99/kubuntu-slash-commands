#!/usr/bin/env python3
import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

from evdev import InputDevice, UInput, ecodes, list_devices
from PySide6.QtCore import Qt, Signal, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout
from PySide6.QtGui import QDesktopServices

BASE = Path(__file__).resolve().parent
COMMANDS_FILE = BASE / "commands.json"
DOUBLE_SLASH_MS = 280
SLASH = ecodes.KEY_SLASH

class Bus(QObject):
    trigger = Signal()
    status = Signal(str)

class Palette(QDialog):
    def __init__(self, commands, bus):
        super().__init__()
        self.commands = commands
        self.bus = bus
        self.setWindowTitle("Slash Commands")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(620)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("command query…")
        self.list = QListWidget()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        layout.addWidget(self.edit)
        layout.addWidget(self.list)

        self.setStyleSheet("""
            QDialog {
                background: rgba(7, 26, 28, 245);
                border: 1px solid rgba(80, 227, 212, 80);
                border-radius: 16px;
            }
            QLineEdit {
                background: rgba(10, 37, 39, 230);
                border: 1px solid rgba(80, 227, 212, 45);
                border-radius: 10px;
                padding: 13px;
                color: #d9fffa;
                font-size: 17px;
            }
            QListWidget {
                background: transparent;
                border: 0;
                color: #d9fffa;
                outline: 0;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 9px;
            }
            QListWidget::item:selected {
                background: rgba(22, 124, 120, 150);
            }
        """)

        self.edit.textChanged.connect(self.refresh)
        self.edit.returnPressed.connect(self.run_selected)
        self.edit.installEventFilter(self)
        self.list.itemActivated.connect(self.run_item)
        self.refresh()

    def show_palette(self):
        self.edit.clear()
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()

    def refresh(self):
        raw = self.edit.text().strip()
        name = raw.split(maxsplit=1)[0].lower() if raw else ""
        self.list.clear()
        for command, data in self.commands.items():
            if not name or name in command.lower() or name in data["description"].lower():
                item = QListWidgetItem(f"/{command}    {data['description']}")
                item.setData(Qt.UserRole, command)
                self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def run_selected(self):
        item = self.list.currentItem()
        if item:
            self.run_item(item)

    def run_item(self, item):
        command = item.data(Qt.UserRole)
        raw = self.edit.text().strip()
        parts = raw.split(maxsplit=1)
        query = parts[1] if len(parts) == 2 else ""
        template = self.commands[command]["url"]
        url = template.replace("{query}", quote(query, safe=""))
        self.hide()
        QDesktopServices.openUrl(QUrl(url))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

class KeyboardBridge:
    def __init__(self, bus):
        self.bus = bus
        self.stop = False
        self.active = False
        self.devices = []
        self.uinput = None
        self.pending = []
        self.pending_since = 0.0
        self.lock = threading.Lock()

    def start(self):
        keyboards = []
        for path in list_devices():
            try:
                dev = InputDevice(path)
                keys = dev.capabilities().get(ecodes.EV_KEY, [])
                if SLASH in keys and any(k < ecodes.BTN_MISC for k in keys):
                    keyboards.append(dev)
            except Exception:
                pass

        if not keyboards:
            raise RuntimeError("No accessible keyboard devices found. Check that your user is in the input group.")

        # One virtual keyboard forwards the physical keyboard events after
        # we have decided whether the slash sequence is a command.
        self.uinput = UInput(
            {ecodes.EV_KEY: list(range(1, 768))},
            name="Kubuntu Slash Commands Virtual Keyboard"
        )

        for dev in keyboards:
            self.devices.append(dev)
            threading.Thread(target=self.read_device, args=(dev,), daemon=True).start()

        self.bus.status.emit(f"Monitoring {len(keyboards)} keyboard(s)")

    def emit(self, event):
        if event.type == ecodes.EV_SYN:
            self.uinput.syn()
        elif event.type == ecodes.EV_KEY:
            self.uinput.write_event(event)

    def flush_pending(self):
        for event in self.pending:
            self.emit(event)
        self.pending.clear()
        self.pending_since = 0.0

    def read_device(self, dev):
        try:
            dev.grab()
            for event in dev.read_loop():
                with self.lock:
                    if self.stop:
                        break

                    now = time.monotonic()

                    if self.active:
                        self.emit(event)
                        continue

                    if event.type == ecodes.EV_KEY and event.code == SLASH:
                        if event.value == 1:
                            if self.pending and (now - self.pending_since) <= DOUBLE_SLASH_MS / 1000:
                                # Second slash: suppress both slashes and open.
                                self.pending.clear()
                                self.pending_since = 0.0
                                self.active = True
                                self.bus.trigger.emit()
                            elif self.pending:
                                self.flush_pending()
                                self.pending.append(event)
                                self.pending_since = now
                            else:
                                self.pending.append(event)
                                self.pending_since = now
                        else:
                            if self.pending:
                                self.pending.append(event)
                            else:
                                self.emit(event)
                    else:
                        if self.pending:
                            self.flush_pending()
                        self.emit(event)

                    if self.pending and now - self.pending_since > DOUBLE_SLASH_MS / 1000:
                        self.flush_pending()
        except Exception as exc:
            self.bus.status.emit(f"{dev.name}: {exc}")
        finally:
            try:
                dev.ungrab()
            except Exception:
                pass

    def resume(self):
        with self.lock:
            self.active = False

    def shutdown(self):
        with self.lock:
            self.stop = True
            self.flush_pending()
        for dev in self.devices:
            try:
                dev.ungrab()
                dev.close()
            except Exception:
                pass
        if self.uinput:
            self.uinput.close()

def load_commands():
    with open(COMMANDS_FILE, encoding="utf-8") as f:
        return json.load(f)

def main():
    app = QApplication(sys.argv)
    bus = Bus()
    commands = load_commands()
    palette = Palette(commands, bus)
    bridge = KeyboardBridge(bus)

    def trigger():
        palette.show_palette()

    def hidden():
        bridge.resume()

    bus.trigger.connect(trigger)
    palette.finished.connect(lambda _: bridge.resume())
    palette.rejected.connect(hidden)

    try:
        bridge.start()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    def on_hide():
        if not palette.isVisible():
            bridge.resume()

    app.aboutToQuit.connect(bridge.shutdown)
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
