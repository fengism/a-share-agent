import type { IChartApi } from "lightweight-charts";

/**
 * 价格 / 成交量双窗格布局约定（K 线与分时图共用）。
 *
 * 为什么两个窗格都用右轴、左轴整体关闭：
 * lightweight-charts 5.2.1 判断"要不要画坐标轴"时只读 **0 号窗格**的 `visible`
 * （`ChartWidget._private__isLeftAxisVisible`），却对**所有**窗格做
 * `ensureNotNull(轴 widget)`；而轴 widget 是否创建又由**每个窗格自己**的 `visible`
 * 决定（`PaneWidget._private__recreatePriceAxisWidgets`）。两者口径不一致，于是
 * 在非 0 窗格单独隐藏任一坐标轴，会让每帧 draw 抛 `Value is null`、整张图不渲染。
 *
 * 所以：可见性只能在 `createChart` 级别统一设置（两个窗格都可见右轴、都不可见左轴），
 * 绝不能对某个窗格单独 `applyOptions({ visible: false })`。
 */

/** 成交量独立窗格序号：0 号窗格放价格与均线，1 号窗格放成交量。 */
export const VOLUME_PANE_INDEX = 1;

/** 价格窗格占绘图区高度的比例，其余留给成交量窗格。 */
export const PRICE_PANE_RATIO = 0.72;

/**
 * 按比例分配窗格高度。
 *
 * 必须用 `setStretchFactor` 而不是 `setHeight`：后者写死像素会把时间轴挤出行高、
 * 导致整图不渲染；前者按比例分配"扣除时间轴后"的剩余高度。
 */
export function applyVolumePaneLayout(chart: IChartApi, ratio: number = PRICE_PANE_RATIO): void {
  const panes = chart.panes();
  if (panes.length > VOLUME_PANE_INDEX) {
    panes[0]?.setStretchFactor(ratio);
    panes[VOLUME_PANE_INDEX]?.setStretchFactor(1 - ratio);
  }
}

/**
 * 窗格分割线（价格主图与成交量副图分界线）与背景网格线的协同视觉配置。
 *
 * 解决"股价和成交量中间的区分线是一条穿越坐标轴的黑线、没有任何说明"的问题：
 * 1. lightweight-charts 内置的 pane separator 是一条贯穿包括右轴的 1px 画布实线，
 *    将其设为 transparent 避免穿透右侧价格轴；
 * 2. 界面改为由独立的量价分界栏组件（VolumeDividerBar）承载：
 *    - 具备独立背景色 (nestedBg) 与细边框；
 *    - 左右边界精确停留在绘图区内部，绝不穿透右轴；
 *    - 显示清晰的「成交量 VOL」标识及实时量额指标说明；
 *    - 支持上下拖拽调整主副图比例；
 * 3. 网格线保持柔化低噪背景。
 */
export function getChartPaneThemeConfig(
  c: { border: string; primary?: string; accent?: string; isLight?: boolean; cardBg?: string },
  isLightOverride?: boolean,
) {
  const isLight = isLightOverride ?? c.isLight ?? (c.cardBg ? c.cardBg !== "#121722" && c.cardBg !== "#101725" : false);
  return {
    panes: {
      enableResize: true,
      separatorColor: "transparent",
      separatorHoverColor: "transparent",
    },
    grid: {
      vertLines: { color: isLight ? "rgba(222, 214, 196, 0.42)" : "rgba(31, 38, 51, 0.45)" },
      horzLines: { color: isLight ? "rgba(222, 214, 196, 0.42)" : "rgba(31, 38, 51, 0.45)" },
    },
  };
}