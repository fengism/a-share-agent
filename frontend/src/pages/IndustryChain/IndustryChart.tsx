import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";

interface IndustryChartProps {
  option: Record<string, unknown>;
  height: string;
}

export default function IndustryChart({ option, height }: IndustryChartProps) {
  return (
    <ReactECharts
      echarts={echarts}
      option={option}
      style={{ height, width: "100%" }}
      notMerge
    />
  );
}
