# Kubuntu Slash Commands

A tiny Chrome/Chromium extension that gives you a fast `//` command palette on web pages.

It is designed for Kubuntu + KDE Plasma + Wayland.

## Example

Rapidly type:

```text
//chatgpt hi
```

A command palette appears. Press Enter and a new tab opens:

```text
https://chatgpt.com/?q=hi
```

The two slashes must be pressed within about **280 ms**.

Normal code comments such as `// comment` continue to work when the slashes are typed normally.

## Included commands

| Command | Example | Action |
| --- | --- | --- |
| `//chatgpt` | `//chatgpt explain recursion` | ChatGPT |
| `//google` | `//google kubuntu kvantum` | Google |
| `//youtube` | `//youtube minecraft` | YouTube |
| `//github` | `//github arch.js` | GitHub |
| `//wiki` | `//wiki KDE Plasma` | Wikipedia |
| `//ddg` | `//ddg linux wayland` | DuckDuckGo |

Commands are defined in `commands.js`.

## Installation on Kubuntu

No root access is required.

### 1. Clone the repository

```bash
git clone https://github.com/Chibbit-99/kubuntu-slash-commands.git
cd kubuntu-slash-commands
```

You can also download the repository as a ZIP and extract it.

### 2. Open the extension manager

In Chrome or Chromium, open:

```text
chrome://extensions
```

### 3. Enable Developer mode

Turn on **Developer mode**.

### 4. Load the extension

Click **Load unpacked** and select the repository directory.

### 5. Test it

Open a normal website, click into the page, and rapidly press `//`.

Then type:

```text
chatgpt hi
```

Press **Enter**.

## Custom commands

Edit `commands.js` and add an object:

```js
{
  name: "example",
  description: "Open Example",
  url: "https://example.com/search?q={query}"
}
```

The `{query}` placeholder is URL-encoded automatically.

After changing commands, reload the extension from `chrome://extensions`.

## Keyboard controls

- `//` quickly — open the palette
- `↑` / `↓` — select a command
- `Enter` — run the command
- `Esc` — close the palette

## Wayland

This project deliberately uses a browser extension rather than a system-wide keyboard hook.

Wayland restricts arbitrary applications from globally observing keyboard input. The extension therefore handles the shortcut on web pages where Chrome allows content scripts to run.

It will not run in browser UI such as the address bar or `chrome://` pages.

## Privacy

The extension does not send command text to a server. It only builds the configured URL locally and asks Chrome to open it.

## License

MIT
