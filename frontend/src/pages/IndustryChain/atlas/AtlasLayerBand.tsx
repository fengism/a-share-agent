import { useColors } from "../../../styles/ui";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import type { AtlasLayer } from "../../../types/stock";
import { LAYER_ACCENTS } from "./constants";

export function AtlasLayerBand({
  layer,
  onCompanyClick,
}: {
  layer: AtlasLayer;
  onCompanyClick: (code: string) => void;
}) {
  const colors = useColors();
  const accentKey = LAYER_ACCENTS[layer.key] || "primary";
  const accent = colors[accentKey];
  const isMobile = useMediaQuery("(max-width: 576px)");

  return (
    <div
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: 12,
        background: colors.cardBg,
        overflow: "hidden",
      }}
    >
      <div
        className="atlas-layer__heading"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: isMobile ? "8px 12px" : "10px 16px",
          borderBottom: `1px solid ${colors.border}`,
          background: `linear-gradient(90deg, ${accent}14, transparent)`,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: 999,
            background: accent,
            boxShadow: `0 0 8px ${accent}`,
            flexShrink: 0,
          }}
        />
        <strong
          className="atlas-layer__name"
          style={{ color: colors.textPrimary, fontSize: isMobile ? "var(--c-font-sm)" : "var(--c-font-base)" }}
        >
          {layer.name}
        </strong>
        <span
          className="atlas-layer__count"
          style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}
        >
          {layer.segments.length} 个环节
        </span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 220px), 1fr))",
          gap: isMobile ? 8 : 12,
          padding: isMobile ? 10 : 14,
        }}
      >
        {layer.segments.map((segment) => (
          <div
            key={segment.name}
            className="atlas-segment"
            style={{
              border: `1px solid ${colors.border}`,
              borderRadius: 10,
              background: colors.nestedBg,
              padding: "var(--c-pad-inset, 7px 12px)",
            }}
          >
            <div
              className="atlas-segment__heading"
              style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}
            >
              <span style={{ width: 3, height: 12, borderRadius: 2, background: accent }} />
              <strong
                className="atlas-segment__name"
                style={{ fontSize: "var(--c-font-md)", color: colors.textPrimary }}
              >
                {segment.name}
              </strong>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {segment.companies.map((company) => (
                <button
                  key={`${company.code}-${company.name}`}
                  type="button"
                  className="atlas-company-chip"
                  title={company.note || company.name}
                  onClick={() => onCompanyClick(company.code)}
                  style={{
                    border: `1px solid ${colors.border}`,
                    background: colors.cardBg,
                    borderRadius: 8,
                    padding: "4px 9px",
                    fontSize: "var(--c-font-sm)",
                    color: colors.textPrimary,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span className="atlas-company-chip__name">{company.name}</span>
                  <span
                    className="financial-num atlas-company-chip__code"
                    style={{ color: accent, fontSize: "var(--c-font-xs)" }}
                  >
                    {company.code}
                  </span>
                  {(company.market === "hk" || company.code.length === 5) && (
                    <span
                      className="atlas-company-chip__market-tag"
                      style={{
                        fontSize: "var(--c-font-xs, 11px)",
                        padding: "1px 4px",
                        borderRadius: 4,
                        background: "rgba(14, 165, 233, 0.12)",
                        color: "#0284c7",
                        fontWeight: 600,
                        lineHeight: 1.2,
                      }}
                    >
                      港股
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
