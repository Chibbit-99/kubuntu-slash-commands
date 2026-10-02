#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="$HOME/.config/systemd/user"
INSTALL_DIR="$HOME/.local/share/kubuntu-slash-commands"

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

sudo tee /etc/udev/rules.d/99-kubuntu-slash-commands.rules >/dev/null <<'EOF'
KERNEL=="uinput", GROUP="input", MODE="0660"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

mkdir -p "$INSTALL_DIR" "$SERVICE_DIR"
cp "$REPO_DIR/slash-launcher.py" "$REPO_DIR/commands.json" "$INSTALL_DIR/"

cat > "$SERVICE_DIR/kubuntu-slash-commands.service" <<EOF
[Unit]
Description=Kubuntu Slash Commands
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/slash-launcher.py
Restart=on-failure
RestartSec=2
Environment=QT_QPA_PLATFORM=wayland

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable kubuntu-slash-commands.service

if [ "$NEEDS_RELOGIN" -eq 1 ]; then
  echo
  echo "Installation is ready, but you must log out and back in once"
  echo "for the input-group permission to take effect."
  echo "After logging back in, the service starts automatically."
else
  systemctl --user restart kubuntu-slash-commands.service
  echo "Kubuntu Slash Commands is running."
fi
