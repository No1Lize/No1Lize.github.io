"use client";

import { Bookmark } from "lucide-react";
import { useEffect, useState } from "react";
import {
  FAVORITES_CHANGED_EVENT,
  FAVORITES_STORAGE_KEY,
  isFavorite,
  toggleFavorite,
  type FavoriteInput,
} from "@/lib/favorites";

export function FavoriteButton({ item }: { item: FavoriteInput }) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const refresh = () => setSaved(isFavorite(item.id));
    const onStorage = (event: StorageEvent) => {
      if (event.key === FAVORITES_STORAGE_KEY) refresh();
    };
    refresh();
    window.addEventListener(FAVORITES_CHANGED_EVENT, refresh);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(FAVORITES_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", onStorage);
    };
  }, [item.id]);

  return (
    <>
      <button
        type="button"
        className="favorite-button detail-favorite-button"
        data-saved={saved ? "true" : "false"}
        aria-pressed={saved}
        aria-label={saved ? `取消收藏：${item.title}` : `收藏：${item.title}`}
        title={saved ? "取消收藏" : "收藏并提高相关关键词与信源的推荐权重"}
        onClick={() => setSaved(toggleFavorite(item))}
      >
        <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
        <span>{saved ? "已收藏" : "收藏"}</span>
      </button>

      <style jsx global>{`
        .detail-title-row {
          position: relative;
          display: block;
          min-width: 0;
          padding-right: 116px;
        }

        .detail-title-row > .detail-favorite-button {
          position: absolute;
          top: 6px;
          right: 0;
          z-index: 5;
          min-width: 96px;
          margin-top: 0;
          border-color: var(--green);
          background: color-mix(in srgb, var(--green) 14%, var(--surface));
          color: var(--green-bright);
          box-shadow: 0 8px 24px color-mix(in srgb, var(--bg) 72%, transparent);
        }

        .detail-title-row > .detail-favorite-button:hover {
          background: color-mix(in srgb, var(--green) 22%, var(--surface));
        }

        @media (max-width: 700px) {
          .detail-title-row {
            padding-right: 50px;
          }

          .detail-title-row > .detail-favorite-button {
            top: 2px;
            width: 40px;
            min-width: 40px;
            padding: 8px;
          }

          .detail-title-row > .detail-favorite-button span {
            display: none;
          }
        }
      `}</style>
    </>
  );
}
