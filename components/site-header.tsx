"use client";

import { Bookmark, Bot, Menu, Search, Settings, X } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

const navItems = [
  ["研究首页", "/"],
  ["核心技术", "/technologies"],
  ["核心赛道", "/technology"],
  ["核心人物", "/people"],
  ["核心公司", "/companies"],
];

export function SiteHeader({ status }: { status: ReactNode }) {
  const [open, setOpen] = useState(false);

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
          {status}
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
          <button className="icon-button mobile-menu" onClick={() => setOpen(!open)} aria-label="展开导航">
            {open ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </div>
    </header>
  );
}
