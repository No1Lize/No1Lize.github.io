"use client";

import { Bookmark, Bot, Menu, Moon, Search, Settings, Sun, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import { LiveStatus } from "@/components/live-status";

const navItems = [
  ["研究首页", "/"],
  ["核心技术", "/technologies"],
  ["核心赛道", "/technology"],
  ["核心人物", "/people"],
  ["核心公司", "/companies"],
];

// The persisted theme lives in localStorage; expose it as an external store
// so the exported (always dark) HTML hydrates cleanly before the stored
// preference is applied, and other tabs stay in sync via storage events.
const THEME_KEY = "lize-theme";
const themeListeners = new Set<() => void>();

function subscribeTheme(callback: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY) callback();
  };
  themeListeners.add(callback);
  window.addEventListener("storage", onStorage);
  return () => {
    themeListeners.delete(callback);
    window.removeEventListener("storage", onStorage);
  };
}

function readTheme() {
  return window.localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
}

export function SiteHeader() {
  const theme = useSyncExternalStore(subscribeTheme, readTheme, () => "dark");
  const dark = theme !== "light";
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  function toggleTheme() {
    window.localStorage.setItem(THEME_KEY, dark ? "light" : "dark");
    for (const listener of themeListeners) listener();
  }

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/" aria-label="丽泽路1号首页">
          <span className="brand-mark">LZ</span>
          <span>
            <strong>丽泽路1号</strong>
            <small>一级市场科技研究</small>
          </span>
        </Link>

        <nav className={open ? "main-nav is-open" : "main-nav"} aria-label="主导航">
          {navItems.map(([label, href], index) => (
            <Link href={href} key={href} onClick={() => setOpen(false)}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              {label}
            </Link>
          ))}
        </nav>

        <div className="header-actions">
          <LiveStatus />
          <Link className="icon-button" href="/research-agent" aria-label="研究助手" title="研究助手">
            <Bot size={18} />
          </Link>
          <Link className="icon-button" href="/favorites" aria-label="收藏" title="收藏">
            <Bookmark size={18} />
          </Link>
          <Link className="icon-button" href="/tracking" aria-label="公开追踪研究" title="公开追踪研究">
            <Settings size={18} />
          </Link>
          <Link className="icon-button" href="/search" aria-label="全局搜索">
            <Search size={18} />
          </Link>
          <button className="icon-button" onClick={toggleTheme} aria-label={dark ? "切换浅色主题" : "切换深色主题"}>
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <button className="icon-button mobile-menu" onClick={() => setOpen(!open)} aria-label="展开导航">
            {open ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </div>
    </header>
  );
}
