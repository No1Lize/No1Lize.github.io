"use client";

import { useSyncExternalStore } from "react";
import {
  getFavoriteIdSnapshot,
  getFavoriteSnapshot,
  subscribeFavorites,
  type FavoriteItem,
} from "@/lib/favorites";

const EMPTY_FAVORITES: FavoriteItem[] = [];
const EMPTY_FAVORITE_IDS = new Set<string>();

function getServerFavorites(): FavoriteItem[] {
  return EMPTY_FAVORITES;
}

function getServerFavoriteIds(): Set<string> {
  return EMPTY_FAVORITE_IDS;
}

export function useFavorites(): FavoriteItem[] {
  return useSyncExternalStore(
    subscribeFavorites,
    getFavoriteSnapshot,
    getServerFavorites,
  );
}

export function useFavorite(id: string): boolean {
  const ids = useSyncExternalStore(
    subscribeFavorites,
    getFavoriteIdSnapshot,
    getServerFavoriteIds,
  );
  return ids.has(id);
}
