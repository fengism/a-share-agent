import type { ThemeColors, DesignTokens } from "../../theme/themes";

/**
 * Shared rank badge used by IndustryRankTab and HotRankContent.
 *
 * Ranks 1-2 use the up (rise) accent; rank 3 uses the warning accent; ranks
 * 4-10 get a tinted warning background. Anything else renders as a muted
 * plain number. Pure render helper — no behavior.
 */
export function rankBadge(rank: number | null, c: ThemeColors, t: DesignTokens) {
  let color = c.textSecondary;
  let bg = "transparent";
  if (rank === 1 || rank === 2) {
    color = c.onPrimary;
    bg = c.up;
  } else if (rank === 3) {
    color = c.onPrimary;
    bg = c.warning;
  } else if (rank !== null && rank <= 10) {
    color = c.warning;
    bg = `${c.warning}26`;
  }

  return (
    <span
      style={{
        display: "inline-block",
        width: 28,
        height: 28,
        lineHeight: "28px",
        textAlign: "center",
        borderRadius: t.radius.md,
        fontWeight: Number(t.weight.bold),
        fontSize: t.font.md,
        color,
        background: bg,
      }}
    >
      {rank ?? "-"}
    </span>
  );
}
