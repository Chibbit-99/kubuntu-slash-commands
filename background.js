chrome.runtime.onMessage.addListener((message, sender) => {
  if (message?.type !== "open-url" || typeof message.url !== "string") return;
  chrome.tabs.create({
    url: message.url,
    index: typeof sender.tab?.index === "number" ? sender.tab.index + 1 : undefined
  });
});
