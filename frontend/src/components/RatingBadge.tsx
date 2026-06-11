import { useColors } from "../styles/ui";

interface Props {
  score: number;
  size?: number;
}

export default function RatingBadge({ score, size = 64 }: Props) {
  const c = useColors();
  const getColor = (s: number) => {
    if (s >= 8) return c.up;
    if (s >= 6) return "#b65c00";
    if (s >= 4) return c.primary;
    return c.down;
  };

  const getBg = (s: number) => {
    if (s >= 8) return "rgba(201,55,44,0.08)";
    if (s >= 6) return "rgba(182,92,0,0.08)";
    if (s >= 4) return "rgba(31,58,95,0.08)";
    return "rgba(31,132,90,0.08)";
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
