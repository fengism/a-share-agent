import type { CSSProperties, ReactNode } from "react";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import ChangeValue from "./ChangeValue";
import "./financial-metric.css";

export interface FinancialMetricProps {
  label: ReactNode;
  value: ReactNode;
  change?: number | null;
  unit?: ReactNode;
  trend?: "auto" | "up" | "down" | "flat" | "neutral";
  tooltip?: ReactNode;
  size?: "small" | "middle" | "large";
  align?: "left" | "right" | "center";
  className?: string;
  style?: CSSProperties;
}

/**
 * 金额 / 财务 / 行情指标统一展示组件。
 *
 * 规范：
 * - 统一使用等宽字体（`var(--c-font-mono)`）与数字紧凑对齐；
 * - 严格遵循 A 股色彩纪律（红涨绿跌）；
 * - 支持标签悬浮提示、单位、涨跌幅联动展示。
 */
export default function FinancialMetric({
  label,
  value,
  change,
  unit,
  trend = "auto",
  tooltip,
  size = "middle",
  align = "left",
  className,
  style,
}: FinancialMetricProps) {
  let trendClass = "";
  if (trend === "up") {
    trendClass = "financial-metric__value--up";
  } else if (trend === "down") {
    trendClass = "financial-metric__value--down";
  } else if (trend === "auto" && typeof change === "number") {
    if (change > 0) trendClass = "financial-metric__value--up";
    else if (change < 0) trendClass = "financial-metric__value--down";
  }

  const rootClass = [
    "financial-metric",
    `financial-metric--size-${size}`,
    align !== "left" ? `financial-metric--align-${align}` : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClass} style={style}>
      <span className="financial-metric__label">
        <span>{label}</span>
        {tooltip ? (
          <Tooltip title={tooltip}>
            <InfoCircleOutlined className="financial-metric__label-info" />
          </Tooltip>
        ) : null}
      </span>
      <div className="financial-metric__value-row">
        <span className={["financial-metric__value financial-num", trendClass].filter(Boolean).join(" ")}>
          {value ?? "--"}
        </span>
        {unit ? <span className="financial-metric__unit">{unit}</span> : null}
        {change != null ? (
          <span className="financial-metric__change">
            <ChangeValue value={change} />
          </span>
        ) : null}
      </div>
    </div>
  );
}
