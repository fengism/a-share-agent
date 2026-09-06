import { Typography } from "antd";
import { useCallback } from "react";
import ChangeValue from "../../components/ChangeValue";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import { changeColor } from "../../utils/format";
import { formatMoney } from "./portfolioFormatters";

const { Text } = Typography;

export function usePortfolioTableRenderers() {
  const colors = useColors();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const renderStock = useCallback((name: string, code: string) => (
    <StockExternalLink
      code={code}
      name={name}
      style={{ display: "inline-block", textAlign: "left" }}
    >
      <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
        <span style={{ color: colors.textPrimary, fontWeight: "var(--c-weight-semibold)" }}>{name || code}</span>
        <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>{code}</span>
      </span>
    </StockExternalLink>
  ), [colors]);
  const renderProfit = useCallback((
    amount: number | null | undefined,
    percent?: number | null,
  ) => {
    if (amount == null) return <Text style={{ color: colors.textMuted }}>待获取行情</Text>;
    return (
      <div style={{ whiteSpace: "nowrap" }}>
        <div style={{ color: changeColor(amount, colors), fontWeight: "var(--c-weight-semibold)" }}>
          {formatMoney(amount)}
        </div>
        {percent === undefined ? null : <ChangeValue value={percent} style={{ fontSize: "var(--c-font-sm)" }} />}
      </div>
    );
  }, [colors]);

  return { colors, isMobile, renderProfit, renderStock };
}

export type PortfolioTableRenderers = ReturnType<typeof usePortfolioTableRenderers>;
