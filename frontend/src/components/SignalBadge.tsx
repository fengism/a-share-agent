import { Tag } from "antd";

const SIGNAL_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  strong_buy: { label: "强烈买入", color: "#ef4444", bg: "rgba(239,68,68,0.15)" },
  buy: { label: "买入", color: "#b65c00", bg: "rgba(182,92,0,0.10)" },
  hold: { label: "持有", color: "#3b82f6", bg: "rgba(59,130,246,0.15)" },
  sell: { label: "卖出", color: "#206a5d", bg: "rgba(32,106,93,0.10)" },
  strong_sell: { label: "强烈卖出", color: "#22c55e", bg: "rgba(34,197,94,0.15)" },
};

interface Props {
  signal: string;
}

export default function SignalBadge({ signal }: Props) {
  const config = SIGNAL_CONFIG[signal] || { label: signal, color: "#9ca3af", bg: "rgba(156,163,175,0.12)" };
  return (
    <Tag
      style={{
        fontSize: 15,
        padding: "4px 16px",
        borderRadius: 6,
        border: `1px solid ${config.color}`,
        background: config.bg,
        color: config.color,
        fontWeight: 600,
      }}
    >
      {config.label}
    </Tag>
  );
}
