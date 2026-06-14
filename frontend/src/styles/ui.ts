/**
 * Shared style tokens for the A-Share Agent UI.
 *
 * All styles are now reactive via hooks — use `useColors()` and `useStyles()`.
 */

// ── Hook-based (reactive) ───────────────────────────────
export { useColors, useStyles } from "../theme/hooks";
export { useThemeStore } from "../theme/store";
export { THEME_LIST } from "../theme/themes";
export type { ThemeKey, ThemeColors } from "../theme/themes";
export { getAntToken } from "../theme/store";
export { getColors } from "../theme/store";
