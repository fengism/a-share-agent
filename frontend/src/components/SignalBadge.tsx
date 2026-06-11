import { Tag } from "antd";
import { useColors } from "../styles/ui";

interface Props {
  signal: string;
}

export default function SignalBadge({ signal }: Props) {
  const c = useColors();

  const SIGNAL_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
    strong_buy: { label: "强烈买入", color: c.up, bg: `${c.up}1a` },
    buy: { label: "买入", color: "#b65c00", bg: "rgba(182,92,0,0.10)" },
    hold: { label: "持有", color: c.primary, bg: `${c.primary}1a` },
    sell: { label: "卖出", color: "#206a5d", bg: "rgba(32,106,93,0.10)" },
    strong_sell: { label: "强烈卖出", color: c.down, bg: `${c.down}1a` },
  };

  const config = SIGNAL_CONFIG[signal] || { label: signal, color: c.textSecondary, bg: "rgba(156,163,175,0.12)" };
  return (
    <Tag
      style={{
        color: config.color,
        background: config.bg,
        border: `1px solid ${config.color}33`,
        borderRadius: 16,
        paddingInline: 12,
        fontWeight: 600,
        fontSize: 13,
      }}
    >
      {config.label}
    </Tag>
  );
}
