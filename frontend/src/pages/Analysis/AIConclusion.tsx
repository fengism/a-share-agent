import { Card, List, Progress, Row, Col, Typography } from "antd";
import RatingBadge from "../../components/RatingBadge";
import SignalBadge from "../../components/SignalBadge";
import type { AnalysisResult } from "../../types/stock";
import { useStyles } from "../../styles/ui";;

const { Text } = Typography;

interface Props {
  result: AnalysisResult;
}

export default function AIConclusion({ result }: Props) {
  const { cardStyle, metricTileStyle } = useStyles();
  const {
    fundamental,
    technical,
    sentiment,
    valuation_view,
    fair_value_range,
    overall_rating,
    overall_summary,
    estimated_price_range,
    signal,
    confidence,
    key_factors,
    risk_warnings,
    current_price,
  } = result;

  const [priceLow, priceHigh] = estimated_price_range;
  const priceChange = current_price && priceLow ? ((priceHigh - current_price) / current_price * 100).toFixed(1) : null;

  const signalTheme =
    signal === "buy"
      ? {
          primary: "#ef4444",
          soft: "rgba(239,68,68,0.12)",
          border: "rgba(239,68,68,0.25)",
          progress: "#ef4444",
        }
      : signal === "sell"
        ? {
            primary: "#22c55e",
            soft: "rgba(34,197,94,0.12)",
            border: "rgba(34,197,94,0.25)",
            progress: "#22c55e",
          }
        : {
            primary: "#3b82f6",
            soft: "rgba(59,130,246,0.12)",
            border: "rgba(59,130,246,0.25)",
            progress: "#3b82f6",
          };

  return (
    <Card
      size="small"
      className="pdf-avoid-break"
      title={<span style={{ fontWeight: 700, fontSize: 15, color: "#e5e7eb", letterSpacing: 0.2 }}>AI 综合结论</span>}
      style={{
        ...cardStyle,
        marginBottom: 16,
        borderTop: `3px solid ${signalTheme.primary}`,
      }}
      styles={{ body: { padding: "20px 24px" } }}
    >
      <div className="pdf-avoid-break" style={{ marginBottom: 18, display: "grid", gap: 12 }}>
        <div style={{ padding: "14px 16px", borderRadius: 10, border: `1px solid ${signalTheme.border}`, background: signalTheme.soft }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>核心研判</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "#e5e7eb", lineHeight: 1.6 }}>{overall_summary}</div>
            </div>
            <SignalBadge signal={signal} />
          </div>
        </div>
        <Row gutter={[12, 12]}>
          <Col xs={24} md={8}>
            <div style={{ padding: "12px 14px", borderRadius: 10, border: "1px solid #1e293b", background: "#1a2332", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>投资要点</div>
              <div style={{ fontSize: 13, lineHeight: 1.8, color: "#9ca3af" }}>{key_factors[0] || "暂无"}</div>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div style={{ padding: "12px 14px", borderRadius: 10, border: "1px solid #1e293b", background: "#1a2332", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>风险要点</div>
              <div style={{ fontSize: 13, lineHeight: 1.8, color: "#9ca3af" }}>{risk_warnings[0] || "暂无"}</div>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div style={{ padding: "12px 14px", borderRadius: 10, border: "1px solid #1e293b", background: "#1a2332", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>估值结论</div>
              <div style={{ fontSize: 13, lineHeight: 1.8, color: "#9ca3af", minHeight: 48 }}>
                {valuation_view && (
                  <span style={{
                    color: valuation_view === "低估" ? "#ef4444" : valuation_view === "高估" ? "#22c55e" : "#3b82f6",
                    fontWeight: 600,
                  }}>
                    {valuation_view}
                  </span>
                )}
                {fair_value_range && fair_value_range[0] != null && (
                  <span> · 公允 ¥{fair_value_range[0].toFixed(2)}-¥{fair_value_range[1].toFixed(2)}</span>
                )}
                {!fair_value_range && (
                  <span>目标区间 ¥{priceLow?.toFixed(2)} - ¥{priceHigh?.toFixed(2)}</span>
                )}
              </div>
            </div>
          </Col>
        </Row>
      </div>

      <Row gutter={[20, 20]}>
        <Col xs={24} lg={7} className="pdf-avoid-break">
          <div style={{ padding: "18px 16px", borderRadius: 12, border: `1px solid ${signalTheme.border}`, background: `linear-gradient(180deg, ${signalTheme.soft} 0%, rgba(17,24,39,0.7) 100%)` }}>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
              <RatingBadge score={overall_rating} size={84} />
            </div>
            <div style={{ ...metricTileStyle, marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>12个月目标区间</Text>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#3b82f6", marginTop: 6 }}>
                ¥{priceLow?.toFixed(2)} - ¥{priceHigh?.toFixed(2)}
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: "#9ca3af" }}>
                当前价格 ¥{current_price?.toFixed(2)}
                {priceChange && (
                  <span style={{ marginLeft: 8, color: Number(priceChange) >= 0 ? "#ef4444" : "#22c55e", fontWeight: 600 }}>
                    {Number(priceChange) >= 0 ? "+" : ""}{priceChange}%
                  </span>
                )}
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>模型置信度</Text>
              <Progress percent={Math.round(confidence * 100)} size="small" strokeColor={signalTheme.progress} style={{ marginTop: 6 }} />
            </div>
          </div>
        </Col>

        <Col xs={24} lg={17} className="pdf-avoid-break">
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {[
              { label: "基本面", score: fundamental.score, summary: fundamental.summary },
              { label: "技术面", score: technical.score, summary: technical.summary },
              { label: "情绪面", score: sentiment.score, summary: sentiment.summary },
            ].map((item) => (
              <Col xs={24} md={8} key={item.label}>
                <div style={{ ...metricTileStyle, padding: "14px 12px", height: "100%", textAlign: "left" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                    <RatingBadge score={item.score} size={44} />
                    <div>
                      <div style={{ fontSize: 12, color: "#9ca3af" }}>{item.label}</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: "#e5e7eb" }}>{item.score.toFixed(1)}</div>
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.7 }}>{item.summary}</div>
                </div>
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 16]} className="pdf-avoid-break">
            <Col xs={24} md={12}>
              <div style={{ padding: "14px 16px", border: "1px solid #ead7d5", background: "linear-gradient(135deg, #1a0f0f, #2d1518)", borderRadius: 10, height: "100%" }}>
                <Text strong style={{ color: "#ef4444", fontSize: 13 }}>看多因素</Text>
                <List
                  size="small"
                  dataSource={key_factors}
                  locale={{ emptyText: "暂无" }}
                  renderItem={(item) => (
                    <List.Item style={{ padding: "4px 0", border: "none", fontSize: 12, color: "#9ca3af" }}>
                      <span style={{ color: "#ef4444", marginRight: 6, fontWeight: 700 }}>+</span>{item}
                    </List.Item>
                  )}
                />
              </div>
            </Col>
            <Col xs={24} md={12}>
              <div style={{ padding: "14px 16px", border: "1px solid #d6e7df", background: "linear-gradient(135deg, #0f1a14, #152d1d)", borderRadius: 10, height: "100%" }}>
                <Text strong style={{ color: "#22c55e", fontSize: 13 }}>风险提示</Text>
                <List
                  size="small"
                  dataSource={risk_warnings}
                  locale={{ emptyText: "暂无" }}
                  renderItem={(item) => (
                    <List.Item style={{ padding: "4px 0", border: "none", fontSize: 12, color: "#9ca3af" }}>
                      <span style={{ color: "#22c55e", marginRight: 6, fontWeight: 700 }}>!</span>{item}
                    </List.Item>
                  )}
                />
              </div>
            </Col>
          </Row>
        </Col>
      </Row>
    </Card>
  );
}
