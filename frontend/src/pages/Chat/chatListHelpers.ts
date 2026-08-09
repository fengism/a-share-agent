export const INITIAL_VISIBLE_MESSAGES = 60;
export const LOAD_EARLIER_STEP = 40;

export function getVisibleMessageStart(total: number, visibleCount: number): number {
  return Math.max(0, total - Math.max(0, visibleCount));
}

export function getNextVisibleCount(
  currentVisibleCount: number,
  total: number,
  step = LOAD_EARLIER_STEP,
): number {
  return Math.min(total, Math.max(0, currentVisibleCount) + Math.max(0, step));
}
