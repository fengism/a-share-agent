import type { CSSProperties } from "react";
import { ArrowDownOutlined, ArrowUpOutlined, MinusOutlined } from "@ant-design/icons";
import { useColors } from "../theme/hooks";
import {
  formatChangeAriaLabel,
  formatSignedPercent,
  getChangeDirection,
} from "../utils/format";

interface ChangeValueProps {
  value: number | null | undefined;
  digits?: number;
  showIcon?: boolean;
  fontWeight?: CSSProperties["fontWeight"];
  style?: CSSProperties;
}

export default function ChangeValue({
  value,
  digits = 2,
  showIcon = false,
  fontWeight = 600,
  style,
}: ChangeValueProps) {
  const colors = useColors();
  const direction = getChangeDirection(value);
  const color = direction === "up"
    ? colors.up
    : direction === "down"
      ? colors.down
      : colors.textSecondary;
  const icon = direction === "up"
    ? <ArrowUpOutlined />
    : direction === "down"
      ? <ArrowDownOutlined />
      : direction === "flat"
        ? <MinusOutlined />
        : null;

  return (
    <span
      className="financial-num"
      aria-label={formatChangeAriaLabel(value, digits)}
      style={{ color, fontWeight, ...style }}
    >
      {showIcon && icon ? <>{icon} </> : null}
      {formatSignedPercent(value, digits)}
    </span>
  );
}
