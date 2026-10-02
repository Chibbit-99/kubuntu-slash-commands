# Kubuntu Slash Commands

A **system-wide `//` command launcher for Kubuntu Plasma Wayland**.

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

The launcher opens:

```
https://chatgpt.com/?q=hi
```

Normal `//` comments still work if the two slashes are not pressed within the 280 ms window.

## Why it works on Wayland

Wayland deliberately prevents ordinary applications from globally reading keyboard events.

For a true system-wide shortcut based on arbitrary keys such as `//`, this project uses Linux's evdev input layer. The daemon temporarily grabs the physical keyboard devices, examines the key events, and forwards them through a virtual keyboard created with uinput. This lets it delay a slash long enough to distinguish a normal slash from the rapid `//` trigger.

The Python evdev API supports exclusive device grabs and uinput event injection. citeturn2search2

### Security warning

**This is a powerful permission.** A process with access to keyboard input can potentially observe everything you type, including passwords.

The daemon itself only uses the events to detect the two-slash sequence and does not record or upload keystrokes, but giving a user access to `/dev/input` is inherently sensitive.

Do not install this if you do not trust the code.

## Installation

Clone the repository:

```bash
git clone https://github.com/Chibbit-99/kubuntu-slash-commands.git
cd kubuntu-slash-commands
```

Run:

```bash
chmod +x install.sh
./install.sh
```

The installer:

1. Installs `python3-evdev` and PySide6.
2. Adds your account to the `input` group.
3. Gives the `input` group access to `/dev/uinput`.
4. Installs the daemon as a systemd **user** service.
5. Starts it automatically with your desktop session.

Because the input-group membership changes your login credentials, **log out and log back in once** after installation.

The evdev documentation notes that accessing event devices generally requires root or membership in the `input` group, and that `UInput` injects keyboard events through Linux's uinput interface. citeturn2search0turn2search2

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

After changing `commands.json`, restart:

```bash
systemctl --user restart kubuntu-slash-commands
```

## Service commands

Check status:

```bash
systemctl --user status kubuntu-slash-commands
```

View logs:

```bash
journalctl --user -u kubuntu-slash-commands -f
```

Stop it:

```bash
systemctl --user stop kubuntu-slash-commands
```

Start it:

```bash
systemctl --user start kubuntu-slash-commands
```

## Uninstall

```bash
./uninstall.sh
```

The uninstall script deliberately does **not** remove your account from the `input` group, because other software may rely on it.

## License

MIT
