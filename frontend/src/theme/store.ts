import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ThemeKey } from "./themes";
import { themes } from "./themes";

interface ThemeState {
  themeKey: ThemeKey;
  setThemeKey: (key: ThemeKey) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      themeKey: "stellar-blue",
      setThemeKey: (key) => set({ themeKey: key }),
    }),
    { name: "a-share-agent-theme" },
  ),
);

/** Get current colors synchronously (for non-hook contexts). */
export function getColors() {
  const key = useThemeStore.getState().themeKey;
  return themes[key].colors;
}

/** Get current Ant Design token overrides. */
export function getAntToken() {
  const key = useThemeStore.getState().themeKey;
  return themes[key].antToken;
}
