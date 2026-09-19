import type { ThemeColors, DesignTokens } from "../theme/themes";

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
  let border = "1px solid transparent";
  let boxShadow: string | undefined;

  if (rank === 1) {
    color = "#fff";
    bg = "linear-gradient(135deg, #ec5d52, #ff7875)";
    boxShadow = "0 0 10px rgba(236, 93, 82, 0.45)";
  } else if (rank === 2) {
    color = "#fff";
    bg = "linear-gradient(135deg, #fa8c16, #ffa940)";
    boxShadow = "0 0 10px rgba(250, 140, 22, 0.4)";
  } else if (rank === 3) {
    color = "#fff";
    bg = "linear-gradient(135deg, #e5a50a, #ffd666)";
    boxShadow = "0 0 8px rgba(229, 165, 10, 0.35)";
  } else if (rank !== null && rank <= 10) {
    color = c.warning;
    bg = `${c.warning}1f`;
    border = `1px solid ${c.warning}40`;
  }

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 26,
        height: 26,
        borderRadius: t.radius.sm,
        fontWeight: 700,
        fontSize: t.font.sm,
        fontFamily: "var(--c-font-mono)",
        fontVariantNumeric: "tabular-nums",
        color,
        background: bg,
        border,
        boxShadow,
      }}
    >
      {rank ?? "-"}
    </span>
  );
}
