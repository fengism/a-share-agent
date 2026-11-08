import { useMemo } from "react";
import { deriveTrajectory } from "./stateTrajectory";
import "./state-trajectory-badge.css";

export interface StateTrajectoryBadgeProps {
  fromState?: string;
  toState?: string;
  trajectory?: string;
  signalTypes?: string[];
  strategies?: string[];
}

interface StateColorConfig {
  bg: string;
  color: string;
  border: string;
}

function resolveStateColor(stateName: string): StateColorConfig {
  const s = stateName.toLowerCase();
  if (s.includes("突破") || s.includes("主升") || s.includes("做多") || s.includes("多头")) {
    return {
      bg: "rgba(239, 68, 68, 0.12)",
      color: "#ef4444",
      border: "rgba(239, 68, 68, 0.35)",
    };
  }
  if (s.includes("回踩") || s.includes("企稳") || s.includes("均线") || s.includes("支撑")) {
    return {
      bg: "rgba(245, 158, 11, 0.12)",
      color: "#f59e0b",
      border: "rgba(245, 158, 11, 0.35)",
    };
  }
  if (s.includes("底") || s.includes("反转") || s.includes("反弹") || s.includes("超跌")) {
    return {
      bg: "rgba(16, 185, 129, 0.12)",
      color: "#10b981",
      border: "rgba(16, 185, 129, 0.35)",
    };
  }
  if (s.includes("蓄势") || s.includes("箱体") || s.includes("初显") || s.includes("候选") || s.includes("观察")) {
    return {
      bg: "rgba(6, 182, 212, 0.12)",
      color: "#06b6d4",
      border: "rgba(6, 182, 212, 0.35)",
    };
  }
  if (s.includes("破位") || s.includes("失效") || s.includes("超买") || s.includes("风险")) {
    return {
      bg: "rgba(244, 63, 94, 0.12)",
      color: "#f43f5e",
      border: "rgba(244, 63, 94, 0.35)",
    };
  }
  return {
    bg: "rgba(100, 116, 139, 0.12)",
    color: "#64748b",
    border: "rgba(100, 116, 139, 0.35)",
  };
}


export default function StateTrajectoryBadge({
  fromState,
  toState,
  trajectory,
  signalTypes,
  strategies,
}: StateTrajectoryBadgeProps) {
  const { from, to } = useMemo(() => {
    let f = fromState;
    let t = toState;
    if (!f && !t && trajectory) {
      const parts = trajectory.split(/➔|->|→/);
      if (parts.length >= 2) {
        f = parts[0].trim();
        t = parts[1].trim();
      } else {
        t = trajectory.trim();
      }
    }
    if (!f && !t && (signalTypes?.length || strategies?.length)) {
      const derived = deriveTrajectory(signalTypes, strategies);
      f = derived.from;
      t = derived.to;
    }
    return { from: f || "观察期", to: t || "信号确立" };
  }, [fromState, toState, trajectory, signalTypes, strategies]);

  const fromConfig = resolveStateColor(from);
  const toConfig = resolveStateColor(to);

  return (
    <div className="state-trajectory-badge" role="status" aria-label={`形态状态轨迹：${from} 到 ${to}`}>
      <span
        className="state-badge state-badge--from"
        style={{
          backgroundColor: fromConfig.bg,
          color: fromConfig.color,
          borderColor: fromConfig.border,
        }}
      >
        {from}
      </span>
      <span className="state-trajectory-arrow">➔</span>
      <span
        className="state-badge state-badge--to"
        style={{
          backgroundColor: toConfig.bg,
          color: toConfig.color,
          borderColor: toConfig.border,
          boxShadow: `0 0 8px ${toConfig.bg}`,
        }}
      >
        {to}
      </span>
    </div>
  );
}
