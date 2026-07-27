"use client";

import { Copy, ExternalLink, Share2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { QRCodeSVG } from "qrcode.react";

type ShareTarget = {
  title: string;
  summary: string;
  url: string;
};

function cleanText(value: string | null | undefined): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function absoluteUrl(value: string): string {
  try {
    return new URL(value, window.location.origin).href;
  } catch {
    return value;
  }
}

function isWechatBrowser(): boolean {
  return /MicroMessenger/i.test(navigator.userAgent);
}

function isWindowsDesktop(): boolean {
  return /Windows/i.test(navigator.userAgent) && !/Mobile|Android|iPhone|iPad/i.test(navigator.userAgent);
}

function targetFromButton(button: HTMLElement): ShareTarget | null {
  const card = button.closest<HTMLElement>(".favorite-intelligence-card, .favorite-card");
  if (!card) return null;
  const link = card.querySelector<HTMLAnchorElement>(
    ".favorite-intelligence-link[href], .favorite-card-main[href]",
  );
  const title = cleanText(card.querySelector("h3, h2")?.textContent);
  const summary = cleanText(
    card.querySelector<HTMLElement>(".event-main > p, .favorite-card-main > p")?.textContent,
  );
  const href = link?.getAttribute("href") || link?.href || "";
  if (!title || !href) return null;
  return { title, summary, url: absoluteUrl(href) };
}

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    textarea.style.pointerEvents = "none";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  }
}

export function WechatShareCompat() {
  const [target, setTarget] = useState<ShareTarget | null>(null);
  const [notice, setNotice] = useState("");
  const [sharing, setSharing] = useState(false);

  const invokeSystemShare = async (item: ShareTarget, urlOnly: boolean) => {
    if (typeof navigator.share !== "function") {
      setNotice("当前浏览器没有系统分享能力，请扫码或复制原始链接。");
      return false;
    }
    const text = item.summary ? `${item.title}\n${item.summary.slice(0, 140)}` : item.title;
    const payload: ShareData = urlOnly
      ? { url: item.url }
      : { title: item.title, text, url: item.url };
    if (typeof navigator.canShare === "function" && !navigator.canShare(payload)) {
      setNotice("当前系统不能接收这类分享数据，请扫码或复制原始链接。");
      return false;
    }
    setSharing(true);
    try {
      await navigator.share(payload);
      return true;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return false;
      setNotice("系统分享没有完成，请改用微信扫码或复制原始链接。");
      return false;
    } finally {
      setSharing(false);
    }
  };

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const element = event.target instanceof Element ? event.target : null;
      const button = element?.closest<HTMLElement>("button.favorite-share");
      if (!button) return;
      const item = targetFromButton(button);
      if (!item) return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      setNotice("");

      if (isWechatBrowser()) {
        setTarget(item);
        const text = `${item.title}${item.summary ? `\n${item.summary.slice(0, 140)}` : ""}\n${item.url}`;
        void copyText(text).then((copied) =>
          setNotice(
            copied
              ? "标题和原链接已复制，请点微信右上角“…”并选择“发送给朋友”或“分享到朋友圈”。"
              : "请点微信右上角“…”并选择“发送给朋友”或“分享到朋友圈”。",
          ),
        );
        return;
      }

      if (isWindowsDesktop()) {
        setTarget(item);
        // 微信 Windows 分享目标对 title + 多行 text + url 的组合载荷兼容不稳定。
        // 只传递一个 URL，避免微信收到无法解析的复合 ShareData。
        void invokeSystemShare(item, true).then((opened) => {
          setNotice(
            opened
              ? "已按微信兼容模式只传递原始链接。若微信客户端仍提示失败，请直接扫码或复制链接。"
              : "请直接扫码或复制原始链接。",
          );
        });
        return;
      }

      void invokeSystemShare(item, false).then((opened) => {
        if (!opened) setTarget(item);
      });
    };

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  if (!target || typeof document === "undefined") return null;

  const copyOriginalLink = async () => {
    const copied = await copyText(target.url);
    setNotice(copied ? "原始链接已复制。" : "复制失败，请点击“打开原始链接”后手动复制。");
  };

  return createPortal(
    <>
      <div
        className="wechat-share-backdrop"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) setTarget(null);
        }}
      >
        <section
          className="wechat-share-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="wechat-share-title"
        >
          <button
            type="button"
            className="wechat-share-close"
            onClick={() => setTarget(null)}
            aria-label="关闭微信分享"
          >
            <X size={18} />
          </button>

          <div className="wechat-share-copy">
            <span>WECHAT SHARE</span>
            <h3 id="wechat-share-title">{target.title}</h3>
            <p>
              Windows 系统分享与微信桌面端之间的接收结果无法由网页确认。本站现在只传递原始 URL，
              并保留手机微信扫码、复制链接和再次重试三种路径。
            </p>
          </div>

          <div className="wechat-share-qr">
            <div>
              <QRCodeSVG
                value={target.url}
                size={212}
                level="M"
                includeMargin
                title={`微信扫码打开：${target.title}`}
              />
            </div>
            <strong>手机微信扫码</strong>
            <p>扫码后直接打开原始情报，再通过微信右上角菜单发送给朋友或分享到朋友圈。</p>
          </div>

          <div className="wechat-share-actions">
            {isWindowsDesktop() ? (
              <button
                type="button"
                disabled={sharing}
                onClick={() => void invokeSystemShare(target, true)}
              >
                <Share2 size={15} />
                {sharing ? "正在打开…" : "再次打开微信兼容分享"}
              </button>
            ) : null}
            <button type="button" onClick={() => void copyOriginalLink()}>
              <Copy size={15} />
              复制原始链接
            </button>
            <a href={target.url} target="_blank" rel="noreferrer">
              <ExternalLink size={15} />
              打开原始链接
            </a>
          </div>

          {notice ? (
            <p className="wechat-share-notice" role="status">
              {notice}
            </p>
          ) : null}
        </section>
      </div>

      <style jsx global>{`
        .wechat-share-backdrop {
          position: fixed;
          inset: 0;
          z-index: 1200;
          display: grid;
          place-items: center;
          padding: 20px;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(8px);
        }

        .wechat-share-dialog {
          position: relative;
          width: min(720px, 94vw);
          max-height: min(760px, 92vh);
          overflow: auto;
          display: grid;
          grid-template-columns: minmax(0, 1fr) 260px;
          gap: 24px;
          padding: 30px;
          border: 1px solid var(--border);
          background: var(--surface);
          box-shadow: var(--shadow);
          color: var(--text);
        }

        .wechat-share-close {
          position: absolute;
          top: 12px;
          right: 12px;
          display: grid;
          place-items: center;
          width: 32px;
          height: 32px;
          border: 1px solid var(--border-soft);
          background: var(--surface-2);
          color: var(--muted);
          cursor: pointer;
        }

        .wechat-share-copy {
          padding-right: 12px;
        }

        .wechat-share-copy > span {
          color: var(--green-bright);
          font: 600 11px/1 Inter, "Noto Sans SC", sans-serif;
          letter-spacing: 0.14em;
        }

        .wechat-share-copy h3 {
          margin: 18px 0 12px;
          font-size: 23px;
          line-height: 1.45;
        }

        .wechat-share-copy p,
        .wechat-share-qr p {
          margin: 0;
          color: var(--muted);
          font-size: 13px;
          line-height: 1.75;
        }

        .wechat-share-qr {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 9px;
          text-align: center;
        }

        .wechat-share-qr > div {
          padding: 8px;
          background: #fff;
        }

        .wechat-share-qr svg {
          display: block;
          max-width: 100%;
          height: auto;
        }

        .wechat-share-qr strong {
          font-size: 14px;
        }

        .wechat-share-actions {
          grid-column: 1 / -1;
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .wechat-share-actions button,
        .wechat-share-actions a {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          min-height: 38px;
          padding: 8px 13px;
          border: 1px solid var(--border);
          background: var(--surface-2);
          color: var(--text);
          cursor: pointer;
          font-size: 12px;
        }

        .wechat-share-actions button:hover,
        .wechat-share-actions a:hover {
          border-color: var(--green);
          color: var(--green-bright);
        }

        .wechat-share-actions button:disabled {
          cursor: wait;
          opacity: 0.65;
        }

        .wechat-share-notice {
          grid-column: 1 / -1;
          margin: 0;
          padding: 10px 12px;
          border-left: 2px solid var(--green);
          background: color-mix(in srgb, var(--green) 8%, var(--surface-2));
          color: var(--text);
          font-size: 12px;
          line-height: 1.65;
        }

        @media (max-width: 720px) {
          .wechat-share-dialog {
            grid-template-columns: 1fr;
            width: min(430px, 96vw);
            padding: 24px 18px;
          }

          .wechat-share-copy {
            padding-right: 22px;
          }

          .wechat-share-copy h3 {
            font-size: 18px;
          }

          .wechat-share-actions {
            flex-direction: column;
          }

          .wechat-share-actions button,
          .wechat-share-actions a {
            width: 100%;
          }
        }
      `}</style>
    </>,
    document.body,
  );
}
