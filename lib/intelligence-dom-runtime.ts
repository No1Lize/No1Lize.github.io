export type IntelligenceDomScope = "favorite" | "capture" | "hotness";

type IntelligenceDomListener = {
  id: number;
  priority: number;
  callback: (rows: readonly HTMLElement[]) => void;
};

const FAVORITE_ROW_SELECTOR = [
  ".event-row",
  ".headlines-column a[class*='feedRow']",
  ".side-column a[class*='feedRow']",
  "[data-intelligence-item]",
  ".material-list > a",
  "a.source-card[href]",
  "a[class*='eventCard'][href]",
  ".market-news-item[href]",
  "[class*='eventList'] > a[href]",
  "[class*='newsList'] > a[href]",
  ".entity-list > a[target='_blank'][href]",
  ".analysis-grid > a[target='_blank'][href]",
].join(",");

const CAPTURE_ROW_SELECTOR = [
  ".event-row",
  "[data-intelligence-item]",
  ".headlines-column a[class*='feedRow']",
  ".side-column a[class*='feedRow']",
  ".material-list > a",
  "a.source-card[href]",
  "a[class*='eventCard'][href]",
  ".market-news-item[href]",
].join(",");

const HOTNESS_ROW_SELECTOR = [
  FAVORITE_ROW_SELECTOR,
  ".favorite-intelligence-card",
  ".favorite-card",
].join(",");

const ALL_ROW_SELECTOR = HOTNESS_ROW_SELECTOR;
const TIMELINE_ROW_SELECTOR = ".timeline > div";

export const INTELLIGENCE_CONTROL_MOUNT_SELECTOR = [
  "[data-intelligence-favorite-mount]",
  "[data-intelligence-hotness-mount]",
  "[data-intelligence-capture-mount]",
].join(",");

const listeners = new Map<number, IntelligenceDomListener>();
let nextListenerId = 1;
let observer: MutationObserver | null = null;
let frame = 0;

function collectRows(): HTMLElement[] {
  const rows = new Set<HTMLElement>();
  document.querySelectorAll<HTMLElement>(ALL_ROW_SELECTOR).forEach((row) => rows.add(row));
  document.querySelectorAll<HTMLElement>(TIMELINE_ROW_SELECTOR).forEach((row) => {
    if (row.querySelector("a[href]")) rows.add(row);
  });
  return [...rows];
}

function isInsideControlMount(node: Node): boolean {
  if (node instanceof Element) {
    return (
      node.matches(INTELLIGENCE_CONTROL_MOUNT_SELECTOR) ||
      Boolean(node.closest(INTELLIGENCE_CONTROL_MOUNT_SELECTOR))
    );
  }
  return Boolean(node.parentElement?.closest(INTELLIGENCE_CONTROL_MOUNT_SELECTOR));
}

export function isControlOnlyMutation(record: MutationRecord): boolean {
  if (isInsideControlMount(record.target)) return true;
  const changedNodes = [...record.addedNodes, ...record.removedNodes];
  return changedNodes.length > 0 && changedNodes.every(isInsideControlMount);
}

function publishRows() {
  frame = 0;
  if (!listeners.size) return;
  const rows = collectRows();
  const ordered = [...listeners.values()].sort(
    (left, right) => left.priority - right.priority || left.id - right.id,
  );
  for (const listener of ordered) listener.callback(rows);
}

function schedulePublish() {
  if (frame || !listeners.size) return;
  frame = window.requestAnimationFrame(publishRows);
}

function ensureObserver() {
  if (observer || typeof document === "undefined" || !document.body) return;
  observer = new MutationObserver((records) => {
    if (records.length > 0 && records.every(isControlOnlyMutation)) return;
    schedulePublish();
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

export function subscribeIntelligenceDom(
  callback: (rows: readonly HTMLElement[]) => void,
  options: { priority?: number } = {},
): () => void {
  const id = nextListenerId;
  nextListenerId += 1;
  listeners.set(id, { id, priority: options.priority ?? 0, callback });
  ensureObserver();
  schedulePublish();

  return () => {
    listeners.delete(id);
    if (listeners.size) return;
    observer?.disconnect();
    observer = null;
    if (frame) window.cancelAnimationFrame(frame);
    frame = 0;
  };
}

export function isIntelligenceDomRow(row: HTMLElement, scope: IntelligenceDomScope): boolean {
  if (row.matches(TIMELINE_ROW_SELECTOR)) return scope !== "capture";
  if (scope === "favorite") return row.matches(FAVORITE_ROW_SELECTOR);
  if (scope === "capture") return row.matches(CAPTURE_ROW_SELECTOR);
  return row.matches(HOTNESS_ROW_SELECTOR);
}
