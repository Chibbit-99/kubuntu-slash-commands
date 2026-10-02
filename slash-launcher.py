#!/usr/bin/env python3
import json
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
DOUBLE_SLASH_SECONDS = 0.280
SLASH = ecodes.KEY_SLASH


class Bus(QObject):
    trigger = Signal()
    resume = Signal()
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
        url = self.commands[command]["url"].replace("{query}", quote(query, safe=""))

        self.hide()
        self.bus.resume.emit()
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
        self.stop = False
        self.active = False
        self.devices = []
        self.uinput = None
        self.pending = []
        self.pending_since = 0.0
        self.pending_timer = None
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
            raise RuntimeError(
                "No accessible keyboard devices found. "
                "Check that your user is in the input group."
            )

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

        if self.pending_timer:
            self.pending_timer.cancel()
            self.pending_timer = None

    def delayed_flush(self):
        with self.lock:
            if self.pending and not self.active and not self.stop:
                self.flush_pending()

    def arm_flush(self):
        if self.pending_timer:
            self.pending_timer.cancel()
        self.pending_timer = threading.Timer(DOUBLE_SLASH_SECONDS, self.delayed_flush)
        self.pending_timer.daemon = True
        self.pending_timer.start()

    def read_device(self, dev):
        try:
            dev.grab()

            for event in dev.read_loop():
                with self.lock:
                    if self.stop:
                        break

                    if self.active:
                        self.emit(event)
                        continue

                    now = time.monotonic()

                    if event.type == ecodes.EV_KEY and event.code == SLASH:
                        if event.value == 1:
                            if self.pending and now - self.pending_since <= DOUBLE_SLASH_SECONDS:
                                self.pending.clear()
                                self.pending_since = 0.0
                                if self.pending_timer:
                                    self.pending_timer.cancel()
                                    self.pending_timer = None
                                self.active = True
                                self.bus.trigger.emit()
                            else:
                                if self.pending:
                                    self.flush_pending()
                                self.pending = [event]
                                self.pending_since = now
                                self.arm_flush()
                        elif self.pending:
                            self.pending.append(event)
                        else:
                            self.emit(event)
                    else:
                        if self.pending:
                            self.flush_pending()
                        self.emit(event)

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
    palette = Palette(load_commands(), bus)
    bridge = KeyboardBridge(bus)

    bus.trigger.connect(palette.show_palette)
    bus.resume.connect(bridge.resume)
    app.aboutToQuit.connect(bridge.shutdown)

    try:
        bridge.start()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
