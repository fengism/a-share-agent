/**
 * ECharts 按需引入：仅注册实际使用的图表组件，减少 bundle 体积。
 *
 * 使用方式：import echarts from "../charts/echarts-setup";
 * 然后将 echarts 实例传给 echarts-for-react 的 echarts prop。
 */

import * as echarts from "echarts/core";
import { BarChart, CandlestickChart, GraphChart, HeatmapChart, LineChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  // Chart types
  BarChart,
  CandlestickChart,
  GraphChart,
  HeatmapChart,
  LineChart,
  // Components
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  // Renderer
  CanvasRenderer,
]);

export default echarts;
