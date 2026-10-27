import { BarChart, GraphChart, LineChart, ScatterChart, TreeChart } from "echarts/charts";
import { MarkLineComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import echarts from "./echarts-setup";

// Register all chart types needed by industry chain research
echarts.use([BarChart, LineChart, ScatterChart, GraphChart, TreeChart, MarkLineComponent, SVGRenderer]);

export default echarts;
