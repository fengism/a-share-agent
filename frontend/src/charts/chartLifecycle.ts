export function shouldFitChartContent(previousViewKey: string | null, nextViewKey: string): boolean {
  return previousViewKey === null || previousViewKey !== nextViewKey;
}

/**
 * Creates a resize handler scheduled via requestAnimationFrame to avoid
 * layout thrashing and high-frequency DOM reflows during window resize.
 */
export function createDebouncedResizeHandler(onResize: (entry: ResizeObserverEntry) => void): (entries: ResizeObserverEntry[]) => void {
  let frameId: number | null = null;
  return ([entry]: ResizeObserverEntry[]) => {
    if (!entry) return;
    if (frameId !== null) {
      cancelAnimationFrame(frameId);
    }
    frameId = requestAnimationFrame(() => {
      frameId = null;
      onResize(entry);
    });
  };
}
