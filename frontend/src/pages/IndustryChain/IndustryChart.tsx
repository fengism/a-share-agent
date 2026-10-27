import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-tree-setup";

interface IndustryChartProps {
  option: Record<string, unknown>;
  height: string;
}

function deserializeFunctions(obj: unknown): unknown {
  if (!obj || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(deserializeFunctions);
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    if (typeof value === "string" && value.startsWith("function(") && value.endsWith("}")) {
      try {
        result[key] = new Function("return " + value)();
      } catch {
        result[key] = value;
      }
    } else {
      result[key] = deserializeFunctions(value);
    }
  }
  return result;
}

export default function IndustryChart({ option, height }: IndustryChartProps) {
  const parsedOption = useMemo(() => deserializeFunctions(option) as Record<string, unknown>, [option]);

  return (
    <ReactECharts
      echarts={echarts}
      option={parsedOption}
      style={{ height, width: "100%" }}
      notMerge
      opts={{ renderer: "svg" }}
    />
  );
}
