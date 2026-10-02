#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"
INSTALL_DIR="$HOME/.local/share/kubuntu-slash-commands"
STATE_DIR="$HOME/.local/state/kubuntu-slash-commands"
INSTALL_USER="$USER"

# Never run the installer with sudo: the user service and desktop session
# must belong to the logged-in user.
if [[ $EUID -eq 0 ]]; then
  echo "Do not run install.sh with sudo. Run: ./install.sh" >&2
  exit 1
fi

echo "Installing Kubuntu Slash Commands..."

sudo apt update
sudo apt install -y python3-evdev python3-pyside6.qtwidgets python3-pyside6.qtgui python3-pyside6.qtcore acl

# uinput is needed for the virtual keyboard used to forward normal typing.
sudo modprobe uinput
echo uinput | sudo tee /etc/modules-load.d/kubuntu-slash-commands.conf >/dev/null

# Give only the installing desktop user access to the physical keyboard event
# nodes and /dev/uinput. This avoids the broad 'input' group and does not
# require a logout/login or manual group configuration.
#
# OWNER is resolved to the real username at install time, so this also works
# for future keyboard hotplug events.
sudo tee /etc/udev/rules.d/99-kubuntu-slash-commands.rules >/dev/null <<EOF
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_KEYBOARD}=="1", OWNER="$INSTALL_USER", MODE="0600"
KERNEL=="uinput", OWNER="$INSTALL_USER", MODE="0600"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input --action=change

mkdir -p "$INSTALL_DIR" "$SERVICE_DIR" "$STATE_DIR"
cp "$REPO_DIR/slash-launcher.py" "$REPO_DIR/commands.json" "$INSTALL_DIR/"
chmod 755 "$INSTALL_DIR/slash-launcher.py"

cat > "$SERVICE_DIR/kubuntu-slash-commands.service" <<EOF
[Unit]
Description=Kubuntu Slash Commands
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/slash-launcher.py
Restart=on-failure
RestartSec=2
Environment=QT_QPA_PLATFORM=wayland
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=%t
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable kubuntu-slash-commands.service
systemctl --user stop kubuntu-slash-commands.service || true
systemctl --user reset-failed kubuntu-slash-commands.service || true
systemctl --user start kubuntu-slash-commands.service

sleep 1

echo
echo "Installed."
echo "Log file: $STATE_DIR/launcher.log"
echo "Journal:  journalctl --user -u kubuntu-slash-commands.service -f"

if systemctl --user is-active --quiet kubuntu-slash-commands.service; then
  echo "Kubuntu Slash Commands is running."
else
  echo
  echo "The service did not stay running. Check:"
  echo "  systemctl --user status kubuntu-slash-commands.service"
  echo "  journalctl --user -u kubuntu-slash-commands.service -n 100 --no-pager"
  echo "  cat $STATE_DIR/launcher.log"
  exit 1
fi
