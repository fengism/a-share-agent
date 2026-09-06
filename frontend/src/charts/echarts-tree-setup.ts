import { GraphChart, TreeChart } from "echarts/charts";
import { SVGRenderer } from "echarts/renderers";
import echarts from "./echarts-setup";

// TreeChart keeps archived reports compatible; new industry-chain charts use GraphChart.
echarts.use([GraphChart, TreeChart, SVGRenderer]);

export default echarts;
