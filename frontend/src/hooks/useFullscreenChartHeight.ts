import { useEffect, useState } from "react";

export interface ChartViewport {
  width: number;
  height: number;
}

/** 全屏弹窗头部 + 安全区预留（像素）。 */
const FULLSCREEN_CHROME_HEIGHT = 88;
/** 竖屏比例与上下限。 */
const PORTRAIT_RATIO = 0.68;
const PORTRAIT_MIN = 360;
const PORTRAIT_MAX = 760;

/**
 * 计算全屏 K 线/分时弹窗内图表的像素高度。
 *
 * 固定高度（如 580px）在手机横屏（例如 844×390）下会超出弹窗可视区并触发滚动；
 * 这里按视口与横竖屏动态计算：横屏铺满视口、竖屏按比例并限制上下限。
 */
export function computeFullscreenChartHeight({ width, height }: ChartViewport): number {
  if (width > height) {
    return Math.max(240, Math.round(height - FULLSCREEN_CHROME_HEIGHT));
  }
  return Math.min(PORTRAIT_MAX, Math.max(PORTRAIT_MIN, Math.round(height * PORTRAIT_RATIO)));
}

function currentViewport(): ChartViewport {
  if (typeof window === "undefined") return { width: 1280, height: 800 };
  return { width: window.innerWidth, height: window.innerHeight };
}

/**
 * 全屏弹窗图表的自适应高度，随 resize / orientationchange 实时更新。
 */
export function useFullscreenChartHeight(): number {
  const [height, setHeight] = useState(() => computeFullscreenChartHeight(currentViewport()));

  useEffect(() => {
    const update = () => setHeight(computeFullscreenChartHeight(currentViewport()));
    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("orientationchange", update);
    };
  }, []);

  return height;
}
