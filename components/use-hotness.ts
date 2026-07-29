"use client";

import { useEffect, useState } from "react";
import {
  HOTNESS_CHANGED_EVENT,
  HOTNESS_STORAGE_KEY,
  readHotnessItems,
  type HotnessItem,
} from "@/lib/hotness";

export function useHotness(): HotnessItem[] {
  const [items, setItems] = useState<HotnessItem[]>([]);

  useEffect(() => {
    const refresh = () => setItems(readHotnessItems());
    const onStorage = (event: StorageEvent) => {
      if (event.key === HOTNESS_STORAGE_KEY) refresh();
    };
    refresh();
    window.addEventListener(HOTNESS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(HOTNESS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  return items;
}
