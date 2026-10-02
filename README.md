# Kubuntu Slash Commands

A **global `//` command launcher for Kubuntu Plasma Wayland**.

This is **not a browser extension**. It runs as a background desktop application and works in browsers, terminals, editors, file managers, and other applications.

## Usage

Rapidly press:

```
//
```

within about **280 ms**.

Then type:

```
chatgpt hi
```

and press Enter.

Normal `/` and `//` input is forwarded normally when the two slashes are not pressed quickly enough.

## How it works

Wayland does not let ordinary applications install arbitrary global keyboard hooks. This project uses Linux's evdev input layer to monitor physical keyboards and uinput to forward their events through a virtual keyboard.

The daemon temporarily grabs the physical keyboard devices, detects the rapid `//` sequence, and forwards everything else. This is why it requires access to `/dev/input` and `/dev/uinput`.

### Security warning

Access to keyboard event devices is sensitive. A process with these permissions can potentially observe everything typed, including passwords.

This project does not record or upload keystrokes, but you should only install it if you trust the code.

## Installation

```bash
git clone https://github.com/Chibbit-99/kubuntu-slash-commands.git
cd kubuntu-slash-commands
chmod +x install.sh
./install.sh
```

The installer:

1. Installs evdev and PySide6.
2. Loads the Linux `uinput` module and makes it persistent.
3. Installs a udev rule that gives **only your account** access to the keyboard event devices and `/dev/uinput`.
4. Installs a systemd **user** service.
5. Enables the service at login.
6. Writes a persistent launcher log to `~/.local/state/kubuntu-slash-commands/launcher.log`.

No `input` group membership, logout/login, or manual input configuration is required. Do not run the installer with `sudo`.

## Troubleshooting

Check whether the service is actually running:

```bash
systemctl --user status kubuntu-slash-commands.service
```

View recent service errors:

```bash
journalctl --user -u kubuntu-slash-commands.service -n 100 --no-pager
```

Follow the live journal:

```bash
journalctl --user -u kubuntu-slash-commands.service -f
```

The launcher also keeps its own log:

```bash
cat ~/.local/state/kubuntu-slash-commands/launcher.log
```

If the service is active but `//` does nothing, check that your current login has input-group access:

```id -nG | tr ' ' '\n' | grep '^input$'
```

If that prints nothing, log out and back in after installation.

## Commands

Commands are configured in `commands.json`.

Default commands:

| Command | Example |
| --- | --- |
| `chatgpt` | `//chatgpt hi` |
| `google` | `//google kubuntu themes` |
| `youtube` | `//youtube minecraft` |
| `github` | `//github arch.js` |
| `wiki` | `//wiki KDE Plasma` |
| `ddg` | `//ddg linux wayland` |

A command is simply:

```json
"example": {
  "description": "Search Example",
  "url": "https://example.com/search?q={query}"
}
```

`{query}` is URL-encoded automatically.

After changing `commands.json`:

```bash
systemctl --user restart kubuntu-slash-commands.service
```

## Uninstall

Run the script as your normal user:

```bash
chmod +x uninstall.sh
./uninstall.sh
```

Or, if the executable bit is missing:

```bash
bash uninstall.sh
```

**Do not run `sudo ./uninstall.sh`.** The systemd command is a user-service command and needs your normal user session.

The uninstall script removes the service, installed files, and udev rule.

## License

MIT
