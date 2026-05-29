import { Card, Col, Row, Tag, Typography } from "antd";
import { useIndicators } from "../../api/queries";
import type { AnalysisResult, TechnicalIndicators } from "../../types/stock";
import RatingBadge from "../../components/RatingBadge";
import { cardStyle, metricTileStyle, metricValueSecondaryStyle, sectionHeaderStyle, tagStyle } from "../../styles/ui";

interface Props {
  code: string;
  analysis?: AnalysisResult | null;
}

const { Paragraph, Text } = Typography;

function getRsiColor(rsi: number | null): string {
  if (rsi === null) return "#9ca3af";
  if (rsi > 70) return "#ef4444";
  if (rsi < 30) return "#22c55e";
  return "#3b82f6";
}

function getMacdSignal(macd: TechnicalIndicators["macd"]): { text: string; color: string } {
  if (macd.dif === null || macd.dea === null) return { text: "-", color: "#9ca3af" };
  if (macd.dif > macd.dea && macd.macd_hist && macd.macd_hist > 0) return { text: "多头", color: "#ef4444" };
  if (macd.dif < macd.dea && macd.macd_hist && macd.macd_hist < 0) return { text: "空头", color: "#22c55e" };
  return { text: "震荡", color: "#3b82f6" };
}

function Indicator({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={metricTileStyle}>
      <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ ...metricValueSecondaryStyle, color: color || "#e5e7eb" }}>{value}</div>
    </div>
  );
}

function renderTags(items: string[] | undefined, color: string) {
  if (!items || items.length === 0) {
    return <Text type="secondary">暂无</Text>;
  }

  return items.map((item) => (
    <Tag key={item} color={color} style={tagStyle}>
      {item}
    </Tag>
  ));
}

export default function TechnicalPanel({ code, analysis }: Props) {
  const { data: indicators, isLoading } = useIndicators(code);

  if (isLoading || !indicators) return null;

  const { ma, macd, rsi, boll, kdj, volume_ma } = indicators;
  const macdSignal = getMacdSignal(macd);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {analysis?.technical && (
        <Card
          size="small"
          style={{ ...cardStyle, marginBottom: 16, borderTop: "3px solid #1f3a5f" }}
          styles={{ body: { padding: 16 } }}
        >
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} sm={6} style={{ textAlign: "center" }}>
              <RatingBadge score={analysis.technical.score} size={64} />
              <div style={{ marginTop: 8, fontWeight: 600, color: "#e5e7eb" }}>技术面评分</div>
              {analysis.technical.trend && (
                <Tag color="blue" style={{ marginTop: 10, borderRadius: 999, paddingInline: 10 }}>
                  趋势：{analysis.technical.trend}
                </Tag>
              )}
            </Col>
            <Col xs={24} sm={18}>
              <Paragraph style={{ marginBottom: 12, color: "#9ca3af", lineHeight: 1.8 }}>
                {analysis.technical.summary}
              </Paragraph>
              <div style={tagStyle}>
                <Text strong style={{ color: "#3b82f6" }}>关键信号：</Text>
              </div>
              <div style={{ marginBottom: 12 }}>
                {renderTags(analysis.technical.key_signals, "blue")}
              </div>
              <Row gutter={12}>
                <Col xs={24} sm={12}>
                  <Card size="small" styles={{ body: { padding: 12 } }}>
                    <Text type="secondary">支撑位</Text>
                    <div style={{ marginTop: 6, fontWeight: 600, fontSize: 18 }}>
                      {analysis.technical.support_level?.toFixed(2) ?? "-"}
                    </div>
                  </Card>
                </Col>
                <Col xs={24} sm={12}>
                  <Card size="small" styles={{ body: { padding: 12 } }}>
                    <Text type="secondary">压力位</Text>
                    <div style={{ marginTop: 6, fontWeight: 600, fontSize: 18 }}>
                      {analysis.technical.resistance_level?.toFixed(2) ?? "-"}
                    </div>
                  </Card>
                </Col>
              </Row>
            </Col>
          </Row>
        </Card>
      )}

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>均线与趋势</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>中短周期趋势判断</Text>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
        <Indicator label="MA5" value={ma.ma5?.toFixed(2) ?? "-"} />
        <Indicator label="MA10" value={ma.ma10?.toFixed(2) ?? "-"} />
        <Indicator label="MA20" value={ma.ma20?.toFixed(2) ?? "-"} />
        <Indicator label="MA60" value={ma.ma60?.toFixed(2) ?? "-"} />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>动量指标</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>MACD、RSI、KDJ 联合观察</Text>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
        <Indicator
          label="MACD信号"
          value={macdSignal.text}
          color={macdSignal.color}
        />
        <Indicator
          label="RSI(14)"
          value={rsi?.toFixed(1) ?? "-"}
          color={getRsiColor(rsi)}
        />
        <Indicator
          label="KDJ"
          value={`K:${kdj.k?.toFixed(1) ?? "-"} D:${kdj.d?.toFixed(1) ?? "-"} J:${kdj.j?.toFixed(1) ?? "-"}`}
        />
        <Indicator
          label="DIF/DEA"
          value={`${macd.dif?.toFixed(2) ?? "-"} / ${macd.dea?.toFixed(2) ?? "-"}`}
        />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>波动区间</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>布林带上下轨观察</Text>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
        <Indicator label="BOLL上轨" value={boll.upper?.toFixed(2) ?? "-"} />
        <Indicator label="BOLL中轨" value={boll.middle?.toFixed(2) ?? "-"} />
        <Indicator label="BOLL下轨" value={boll.lower?.toFixed(2) ?? "-"} />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>量能配合</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>短期成交量均线</Text>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
        <Indicator label="量能MA5" value={volume_ma.ma5?.toFixed(0) ?? "-"} />
        <Indicator label="量能MA10" value={volume_ma.ma10?.toFixed(0) ?? "-"} />
      </div>
    </div>
  );
}
