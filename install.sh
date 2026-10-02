#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"
INSTALL_DIR="$HOME/.local/share/kubuntu-slash-commands"
STATE_DIR="$HOME/.local/state/kubuntu-slash-commands"

echo "Installing Kubuntu Slash Commands..."

sudo apt update
sudo apt install -y python3-evdev python3-pyside6.qtwidgets python3-pyside6.qtgui python3-pyside6.qtcore

sudo groupadd -f input
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  echo "Adding $USER to the input group..."
  sudo usermod -aG input "$USER"
  NEEDS_RELOGIN=1
else
  NEEDS_RELOGIN=0
fi

sudo modprobe uinput
echo uinput | sudo tee /etc/modules-load.d/kubuntu-slash-commands.conf >/dev/null

sudo tee /etc/udev/rules.d/99-kubuntu-slash-commands.rules >/dev/null <<'EOF'
KERNEL=="uinput", GROUP="input", MODE="0660"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

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

echo
echo "Installed."
echo "Log file: $STATE_DIR/launcher.log"
echo "Journal:  journalctl --user -u kubuntu-slash-commands.service -f"

if [ "$NEEDS_RELOGIN" -eq 1 ]; then
  echo
  echo "IMPORTANT: log out and back in once before starting the service."
  echo "The input-group permission is not active in the current login session."
else
  systemctl --user restart kubuntu-slash-commands.service
  sleep 1
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
fi
