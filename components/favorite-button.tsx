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
    <button
      type="button"
      className="favorite-button"
      data-saved={saved ? "true" : "false"}
      aria-pressed={saved}
      aria-label={saved ? `取消收藏：${item.title}` : `收藏：${item.title}`}
      title={saved ? "取消收藏" : "收藏并提高相关关键词与信源的推荐权重"}
      onClick={() => setSaved(toggleFavorite(item))}
    >
      <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
      <span>{saved ? "已收藏" : "收藏"}</span>
    </button>
  );
}
