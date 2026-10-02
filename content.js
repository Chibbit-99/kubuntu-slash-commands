(() => {
  const WINDOW_MS = 280;
  let timer = 0;
  let palette = null;

  const editable = (el) =>
    el instanceof HTMLTextAreaElement ||
    el instanceof HTMLInputElement ||
    !!el?.isContentEditable;

  function showPalette() {
    clearTimeout(timer);
    timer = 0;
    if (palette) return;

    palette = document.createElement("div");
    palette.id = "kubuntu-slash-overlay";
    palette.innerHTML =
      '<div id="kubuntu-slash-window">' +
      '<div id="kubuntu-slash-input-wrap"><span id="kubuntu-slash-prefix">//</span>' +
      '<input id="kubuntu-slash-input" autocomplete="off" spellcheck="false" placeholder="command and query…"></div>' +
      '<div id="kubuntu-slash-results"></div>' +
      '<div id="kubuntu-slash-hint">↑ ↓ select · Enter open · Esc close</div></div>';
    document.documentElement.appendChild(palette);

    const field = palette.querySelector("#kubuntu-slash-input");
    field.addEventListener("input", () => render(field));
    field.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        palette.remove();
        palette = null;
      } else if (event.key === "Enter") {
        event.preventDefault();
        run(field.value.trim());
      }
    });
    render(field);
    field.focus();
  }

  function render(field) {
    const value = field.value.trim().toLowerCase();
    const results = palette.querySelector("#kubuntu-slash-results");
    results.textContent = "";

    const commands = (globalThis.SLASH_COMMANDS || []).filter((command) =>
      !value || (command.name + " " + command.description).toLowerCase().includes(value.split(/\s+/)[0])
    );

    commands.forEach((command, index) => {
      const button = document.createElement("button");
      button.className = "kubuntu-slash-item" + (index === 0 ? " selected" : "");
      button.innerHTML =
        '<span class="kubuntu-slash-item-icon">/</span>' +
        '<span class="kubuntu-slash-item-main">' +
        '<span class="kubuntu-slash-item-name">/' + command.name + '</span>' +
        '<span class="kubuntu-slash-item-description">' + command.description + '</span>' +
        '</span>';
      button.addEventListener("click", () => run(field.value.trim()));
      results.appendChild(button);
    });

    if (!commands.length) {
      const empty = document.createElement("div");
      empty.id = "kubuntu-slash-empty";
      empty.textContent = "No matching commands.";
      results.appendChild(empty);
    }
  }

  function run(text) {
    if (!text) return;
    const parts = text.split(/\s+/);
    const name = parts.shift().toLowerCase();
    const command = (globalThis.SLASH_COMMANDS || []).find((item) => item.name === name);
    if (!command) return;

    const url = command.url.replaceAll("{query}", encodeURIComponent(parts.join(" ")));
    palette?.remove();
    palette = null;
    chrome.runtime.sendMessage({ type: "open-url", url });
  }

  document.addEventListener("keydown", (event) => {
    if (palette || event.defaultPrevented || event.isComposing) return;
    if (event.key !== "/" || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;

    if (timer) {
      clearTimeout(timer);
      timer = 0;
      event.preventDefault();
      showPalette();
      return;
    }

    // For editable fields, hold the first slash briefly so a fast // can
    // become a command without leaving a stray slash in the field.
    if (editable(event.target)) {
      event.preventDefault();
      timer = setTimeout(() => {
        timer = 0;
        if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
          const start = event.target.selectionStart ?? event.target.value.length;
          const end = event.target.selectionEnd ?? start;
          event.target.setRangeText("/", start, end, "end");
          event.target.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: "/" }));
        } else {
          document.execCommand("insertText", false, "/");
        }
      }, WINDOW_MS);
    } else {
      timer = setTimeout(() => { timer = 0; }, WINDOW_MS);
    }
  }, true);
})();
