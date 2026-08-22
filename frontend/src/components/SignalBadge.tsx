import { Tag } from "antd";
import { useColors, useTokens } from "../styles/ui";

interface Props {
  signal: string;
}

export default function SignalBadge({ signal }: Props) {
  const c = useColors();
  const t = useTokens();

  const SIGNAL_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
    strong_buy: { label: "重点关注", color: c.success, bg: `${c.success}1a` },
    buy: { label: "关注", color: c.success, bg: `${c.success}1a` },
    hold: { label: "观察", color: c.primary, bg: `${c.primary}1a` },
    sell: { label: "谨慎", color: c.up, bg: `${c.up}1a` },
    strong_sell: { label: "回避", color: c.up, bg: `${c.up}1a` },
  };

  const config = SIGNAL_CONFIG[signal] || { label: signal, color: c.textSecondary, bg: `${c.textSecondary}1f` };
  return (
    <Tag
      style={{
        color: config.color,
        background: config.bg,
        border: `1px solid ${config.color}33`,
        borderRadius: t.radius.lg,
        paddingInline: t.space[3],
        fontWeight: Number(t.weight.semibold),
        fontSize: t.font.md,
      }}
    >
      {config.label}
    </Tag>
  );
}
