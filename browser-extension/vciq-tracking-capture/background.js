const CAPTURE_URL = "https://vciq.github.io/tracking/capture/";

const MENU_ITEMS = [
  {
    id: "vciq-capture-page",
    title: "采集当前网页到 VCIQ",
    contexts: ["page"],
  },
  {
    id: "vciq-capture-company",
    title: "将选中文字作为公司追踪",
    contexts: ["selection"],
  },
  {
    id: "vciq-capture-person",
    title: "将选中文字作为人物追踪",
    contexts: ["selection"],
  },
  {
    id: "vciq-capture-topic",
    title: "将选中文字作为技术／主题追踪",
    contexts: ["selection"],
  },
];

function entityTypeForMenu(id) {
  if (id === "vciq-capture-company") return "company";
  if (id === "vciq-capture-person") return "person";
  if (id === "vciq-capture-topic") return "topic";
  return "";
}

function publicPageUrl(info, tab) {
  const candidate = info.pageUrl || tab?.url || "";
  try {
    const url = new URL(candidate);
    return url.protocol === "http:" || url.protocol === "https:"
      ? url.toString()
      : "";
  } catch {
    return "";
  }
}

function buildCaptureUrl(info = {}, tab = {}, entityType = "") {
  const pageUrl = publicPageUrl(info, tab);
  if (!pageUrl) return "";
  const target = new URL(CAPTURE_URL);
  target.searchParams.set("url", pageUrl);
  target.searchParams.set("title", String(tab.title || pageUrl).slice(0, 300));
  const selection = String(info.selectionText || "").trim().slice(0, 800);
  if (selection) target.searchParams.set("selection", selection);
  if (entityType) target.searchParams.set("type", entityType);
  try {
    target.searchParams.set("source", new URL(pageUrl).hostname.replace(/^www\./i, ""));
  } catch {
    // The URL has already passed validation; keep source optional if parsing fails.
  }
  return target.toString();
}

function openCapture(info, tab, entityType = "") {
  const url = buildCaptureUrl(info, tab, entityType);
  if (url) chrome.tabs.create({ url });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    for (const item of MENU_ITEMS) chrome.contextMenus.create(item);
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  openCapture(info, tab, entityTypeForMenu(info.menuItemId));
});

chrome.action.onClicked.addListener((tab) => {
  openCapture({ pageUrl: tab.url || "" }, tab);
});
