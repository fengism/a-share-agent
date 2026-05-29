interface Props {
  score: number;
  size?: number;
}

export default function RatingBadge({ score, size = 64 }: Props) {
  const getColor = (s: number) => {
    if (s >= 8) return "#ef4444";
    if (s >= 6) return "#b65c00";
    if (s >= 4) return "#3b82f6";
    return "#22c55e";
  };

  const getBg = (s: number) => {
    if (s >= 8) return "rgba(201,55,44,0.08)";
    if (s >= 6) return "rgba(182,92,0,0.08)";
    if (s >= 4) return "rgba(31,58,95,0.08)";
    return "rgba(31,132,90,0.08)";
  };

  const getLabel = (s: number) => {
    if (s >= 8) return "强势";
    if (s >= 6) return "偏多";
    if (s >= 4) return "中性";
    return "偏空";
  };

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        backgroundColor: getBg(score),
        border: `2px solid ${getColor(score)}`,
        color: getColor(score),
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 700,
      }}
    >
      <span style={{ fontSize: size * 0.38, lineHeight: 1 }}>{score}</span>
      <span style={{ fontSize: size * 0.14, lineHeight: 1, opacity: 0.85 }}>{getLabel(score)}</span>
    </div>
  );
}
