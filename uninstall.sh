#!/usr/bin/env bash
set -euo pipefail

systemctl --user disable --now kubuntu-slash-commands.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/kubuntu-slash-commands.service"
rm -rf "$HOME/.local/share/kubuntu-slash-commands"

sudo rm -f /etc/udev/rules.d/99-kubuntu-slash-commands.rules
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "Kubuntu Slash Commands removed."
echo "The input group was not removed because other applications may use it."
