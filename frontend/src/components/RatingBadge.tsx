import { useColors } from "../styles/ui";

interface Props {
  score: number;
  size?: number;
}

export default function RatingBadge({ score, size = 64 }: Props) {
  const c = useColors();
  const getColor = (s: number) => {
    if (s >= 8) return c.up;
    if (s >= 6) return c.warning;
    if (s >= 4) return c.primary;
    return c.down;
  };

  // Background tint tracks the border color exactly (8% alpha via hex "14"
  // suffix) so fill and ring stay in the same hue across both themes.
  const getBg = (s: number) => {
    if (s >= 8) return `${c.up}14`;
    if (s >= 6) return `${c.warning}14`;
    if (s >= 4) return `${c.primary}14`;
    return `${c.down}14`;
  };

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: getBg(score),
        border: `2px solid ${getColor(score)}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        flexShrink: 0,
      }}
    >
      <span style={{ fontSize: size * 0.3, fontWeight: 800, color: getColor(score), lineHeight: 1 }}>
        {score.toFixed(1)}
      </span>
      <span style={{ fontSize: size * 0.13, color: c.textMuted, marginTop: 2 }}>/ 10</span>
    </div>
  );
}
