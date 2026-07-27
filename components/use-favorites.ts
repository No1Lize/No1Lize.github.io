"use client";

import { useEffect, useState } from "react";
import {
  FAVORITES_CHANGED_EVENT,
  FAVORITES_STORAGE_KEY,
  readFavoriteItems,
  type FavoriteItem,
} from "@/lib/favorites";

export function useFavorites(): FavoriteItem[] {
  const [favorites, setFavorites] = useState<FavoriteItem[]>([]);

  useEffect(() => {
    const refresh = () => setFavorites(readFavoriteItems());
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
  }, []);

  return favorites;
}
