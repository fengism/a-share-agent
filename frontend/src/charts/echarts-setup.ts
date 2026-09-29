/**
 * ECharts 按需引入：仅注册实际使用的图表组件，减少 bundle 体积。
 *
 * 使用方式：import echarts from "../charts/echarts-setup";
 * 然后将 echarts 实例传给 echarts-for-react 的 echarts prop。
 */

import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  // Chart types
  BarChart,
  HeatmapChart,
  LineChart,
  // Components
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  // Renderer
  CanvasRenderer,
]);

export default echarts;
