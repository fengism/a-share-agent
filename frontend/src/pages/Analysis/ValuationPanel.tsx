import { Card, Col, Row, Spin, Table, Tag, Typography } from "antd";
import { useValuationDetail } from "../../api/queries";
import type { AnalysisResult, DCFValuationResult, InstitutionForecast, StockValuationPeer, ValuationMethodResult } from "../../types/stock";
import { cardStyle, metricTileStyle, metricValueEmphasisStyle, sectionCardBodyStyle, sectionHeaderStyle, tagStyle } from "../../styles/ui";

interface Props {
  code: string;
  analysis?: AnalysisResult | null;
}

const { Paragraph, Text } = Typography;

function formatAmount(value: number | null | undefined) {
  if (value == null) return "-";
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)}万`;
  return value.toFixed(2);
}

function formatPercent(value: number | null | undefined) {
  if (value == null) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function percentileTag(value: number | null | undefined) {
  if (value == null) return <Text type="secondary">-</Text>;
  if (value < 30) return <Tag color="green" style={tagStyle}>偏低 {value.toFixed(1)}%</Tag>;
  if (value <= 70) return <Tag color="orange" style={tagStyle}>中位 {value.toFixed(1)}%</Tag>;
  return <Tag color="red" style={tagStyle}>偏高 {value.toFixed(1)}%</Tag>;
}

function valuationViewTag(value: string | null | undefined) {
  if (!value) return <Text type="secondary">-</Text>;
  if (value === "低估") return <Tag color="green" style={tagStyle}>{value}</Tag>;
  if (value === "高估") return <Tag color="red" style={tagStyle}>{value}</Tag>;
  return <Tag color="blue" style={tagStyle}>{value}</Tag>;
}

function formatPriceRange(value: number[] | null | undefined) {
  if (!value || value.length !== 2) return "-";
  return `¥${value[0].toFixed(2)} - ¥${value[1].toFixed(2)}`;
}

function formatWeight(value: number | null | undefined) {
  if (value == null) return "-";
  return `${(value * 100).toFixed(0)}%`;
}

function formatConfidence(value: number | null | undefined) {
  if (value == null) return "-";
  return `${(value * 100).toFixed(0)}%`;
}

function renderMethodCard(title: string, item: ValuationMethodResult | DCFValuationResult | undefined) {
  return (
    <div style={metricTileStyle}>
      <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>{title}</div>
      <div style={{ ...metricValueEmphasisStyle, marginBottom: 8 }}>
        {item?.available ? `¥${item.per_share_value?.toFixed(2) ?? "-"}` : "不可用"}
      </div>
      <Paragraph style={{ margin: 0, fontSize: 12, color: "#9ca3af" }}>
        {item?.available ? `区间 ${formatPriceRange(item.value_range)}` : (item?.reason ?? "-")}
      </Paragraph>
      <div style={{ display: "flex", justifyContent: "center", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
        <Tag color="blue" style={{ ...tagStyle, marginBottom: 0 }}>权重 {formatWeight(item?.weight)}</Tag>
        <Tag color="purple" style={{ ...tagStyle, marginBottom: 0 }}>置信 {formatConfidence(item?.confidence_score)}</Tag>
      </div>
      <Paragraph style={{ margin: "8px 0 0", fontSize: 12, color: "#9ca3af" }}>
        {item?.available ? `相对现价 ${formatPercent(item.upside_pct)}` : item?.applicability}
      </Paragraph>
      {item?.applicability && item.available && (
        <Paragraph style={{ margin: "8px 0 0", fontSize: 12, color: "#9ca3af" }}>
          {item.applicability}
        </Paragraph>
      )}
      {item?.basis && (
        <Paragraph style={{ margin: "8px 0 0", fontSize: 12, color: "#9ca3af" }}>
          {item.basis}
        </Paragraph>
      )}
    </div>
  );
}

export default function ValuationPanel({ code }: Props) {
  const { data: detail, isLoading } = useValuationDetail(code);

  const peerColumns = [
    { title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>名称</span>, dataIndex: "name", key: "name", render: (value: string) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{value}</span> },
    { title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>代码</span>, dataIndex: "code", key: "code", render: (value: string) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{value}</span> },
    {
      title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>PE(TTM)</span>,
      dataIndex: "pe_ttm",
      key: "pe_ttm",
      align: "right" as const, render: (value: number | null) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{value != null ? value.toFixed(2) : "-"}</span>,
    },
    {
      title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>PB</span>,
      dataIndex: "pb",
      key: "pb",
      align: "right" as const, render: (value: number | null) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{value != null ? value.toFixed(2) : "-"}</span>,
    },
    {
      title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>PS(TTM)</span>,
      dataIndex: "ps_ttm",
      key: "ps_ttm",
      align: "right" as const, render: (value: number | null) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{value != null ? value.toFixed(2) : "-"}</span>,
    },
  ];

  if (isLoading) return <Spin />;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card size="small" title="当前估值快照" style={{ ...cardStyle, marginBottom: 16, borderTop: "3px solid #1f3a5f" }} styles={{ body: { ...sectionCardBodyStyle, padding: "16px 20px" } }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>PE(TTM)</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.pe_ttm?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: 8 }}>{percentileTag(detail?.percentiles.pe_3y)}</div>
            </div>
          </Col>
          <Col xs={24} md={6}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>PB</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.pb?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: 8 }}>{percentileTag(detail?.percentiles.pb_3y)}</div>
            </div>
          </Col>
          <Col xs={24} md={6}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>PS(TTM)</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.ps_ttm?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: 8 }}>{percentileTag(detail?.percentiles.ps_3y)}</div>
            </div>
          </Col>
          <Col xs={24} md={6}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>PEG</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.peg?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: 8, color: "#9ca3af", fontSize: 12 }}>成长匹配度</div>
            </div>
          </Col>
          <Col xs={24} md={6}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>股票画像</div>
              <div style={{ ...metricValueEmphasisStyle, fontSize: 18 }}>{detail?.profile?.label ?? "-"}</div>
              <div style={{ marginTop: 8 }}>{valuationViewTag(detail?.valuation_view)}</div>
            </div>
          </Col>
        </Row>
      </Card>

      <Card size="small" title="动态估值结论" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { ...sectionCardBodyStyle, padding: "16px 20px" } }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>合理估值区间</div>
              <div style={{ ...metricValueEmphasisStyle, fontSize: 18 }}>{formatPriceRange(detail?.fair_value_range)}</div>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>加权中枢</div>
              <div style={{ ...metricValueEmphasisStyle, fontSize: 18 }}>{detail?.blended_fair_value != null ? `¥${detail.blended_fair_value.toFixed(2)}` : "-"}</div>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div style={metricTileStyle}>
              <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 4 }}>方法权重</div>
              <div style={{ display: "flex", gap: 6, justifyContent: "center", flexWrap: "wrap" }}>
                {Object.entries(detail?.method_weights ?? {}).map(([method, weight]) => (
                  <Tag key={method} style={{ ...tagStyle, marginBottom: 0 }}>{method.toUpperCase()} {formatWeight(weight)}</Tag>
                ))}
              </div>
            </div>
          </Col>
        </Row>
        {detail?.valuation_summary && (
          <Paragraph style={{ margin: "14px 0 0", color: "#9ca3af" }}>{detail.valuation_summary}</Paragraph>
        )}
      </Card>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>估值方法对比</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>PE / PB / PS / PEG / DCF</Text>
      </div>
      <Card size="small" title="五种估值结果" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { ...sectionCardBodyStyle, padding: "16px 20px" } }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>{renderMethodCard("PE 估值法", detail?.fair_values.pe as ValuationMethodResult | undefined)}</Col>
          <Col xs={24} md={6}>{renderMethodCard("PB 估值法", detail?.fair_values.pb as ValuationMethodResult | undefined)}</Col>
          <Col xs={24} md={6}>{renderMethodCard("PS 估值法", detail?.fair_values.ps as ValuationMethodResult | undefined)}</Col>
          <Col xs={24} md={6}>{renderMethodCard("PEG 估值法", detail?.fair_values.peg as ValuationMethodResult | undefined)}</Col>
          <Col xs={24} md={6}>{renderMethodCard("DCF 估值法", detail?.fair_values.dcf as DCFValuationResult | undefined)}</Col>
        </Row>
      </Card>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>财务基础与关键假设</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>估值参数参考</Text>
      </div>
      <Card size="small" title="关键假设与财务基础" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { ...sectionCardBodyStyle, padding: "16px 20px" } }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: "#9ca3af", fontSize: 12 }}>营收</div><div style={{ fontSize: 18, fontWeight: 600 }}>{formatAmount(detail?.fundamentals.revenue)}</div></div></Col>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: "#9ca3af", fontSize: 12 }}>净利润</div><div style={{ fontSize: 18, fontWeight: 600 }}>{formatAmount(detail?.fundamentals.net_profit)}</div></div></Col>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: "#9ca3af", fontSize: 12 }}>股东权益</div><div style={{ fontSize: 18, fontWeight: 600 }}>{formatAmount(detail?.fundamentals.shareholders_equity)}</div></div></Col>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: "#9ca3af", fontSize: 12 }}>经营现金流</div><div style={{ fontSize: 18, fontWeight: 600 }}>{formatAmount(detail?.fundamentals.operating_cashflow)}</div></div></Col>
        </Row>
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          <Col xs={24} md={8}><div style={metricTileStyle}><div style={{ color: "#9ca3af", fontSize: 12 }}>营收同比</div><div style={{ fontSize: 18, fontWeight: 600 }}>{formatPercent(detail?.fundamentals.revenue_yoy)}</div></div></Col>
          <Col xs={24} md={8}><div style={metricTileStyle}><div style={{ color: "#9ca3af", fontSize: 12 }}>净利润同比</div><div style={{ fontSize: 18, fontWeight: 600 }}>{formatPercent(detail?.fundamentals.net_profit_yoy)}</div></div></Col>
          <Col xs={24} md={8}><div style={metricTileStyle}><div style={{ color: "#9ca3af", fontSize: 12 }}>扣非净利润同比</div><div style={{ fontSize: 18, fontWeight: 600 }}>{formatPercent(detail?.fundamentals.non_net_profit_yoy)}</div></div></Col>
        </Row>
        {detail?.notes?.length ? (
          <div style={{ marginTop: 16 }}>
            {detail.notes.map((note) => (
              <Paragraph key={note} style={{ marginBottom: 6, color: "#9ca3af" }}>{note}</Paragraph>
            ))}
          </div>
        ) : null}
      </Card>

      {detail?.institution_forecasts && detail.institution_forecasts.length > 0 && (
        <>
          <div style={sectionHeaderStyle}>
            <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>机构一致预期</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>EPS / 净利润预测</Text>
          </div>
          <Card size="small" title="机构一致预期" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { padding: "8px 16px" } }}>
            <Table<InstitutionForecast>
              dataSource={detail.institution_forecasts}
              columns={[
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>指标</span>,
                  dataIndex: "metric",
                  key: "metric",
                  render: (v: string) => <Tag style={tagStyle}>{v === "EPS" ? "每股收益" : v === "NET_PROFIT" ? "净利润" : v}</Tag>,
                },
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>年度</span>,
                  dataIndex: "year",
                  key: "year",
                  render: (v: string) => <span style={{ fontSize: 12, color: "#e5e7eb" }}>{v}</span>,
                },
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>机构数</span>,
                  dataIndex: "institution_count",
                  key: "institution_count",
                  align: "right" as const,
                  render: (v: number | null) => <span style={{ fontSize: 12, color: "#3b82f6" }}>{v != null ? v : "-"}</span>,
                },
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>最小值</span>,
                  dataIndex: "min_value",
                  key: "min_value",
                  align: "right" as const,
                  render: (v: number | null) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{v != null ? v.toFixed(2) : "-"}</span>,
                },
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#6366f1" }}>均值</span>,
                  dataIndex: "mean_value",
                  key: "mean_value",
                  align: "right" as const,
                  render: (v: number | null) => <span style={{ fontSize: 13, fontWeight: 600, color: "#6366f1" }}>{v != null ? v.toFixed(2) : "-"}</span>,
                },
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>最大值</span>,
                  dataIndex: "max_value",
                  key: "max_value",
                  align: "right" as const,
                  render: (v: number | null) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{v != null ? v.toFixed(2) : "-"}</span>,
                },
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>行业均值</span>,
                  dataIndex: "industry_avg",
                  key: "industry_avg",
                  align: "right" as const,
                  render: (v: number | null) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{v != null ? v.toFixed(2) : "-"}</span>,
                },
                {
                  title: <span style={{ fontSize: 12, fontWeight: 700, color: "#9ca3af" }}>单位</span>,
                  dataIndex: "unit",
                  key: "unit",
                  render: (v: string | null) => <span style={{ fontSize: 12, color: "#9ca3af" }}>{v ?? "-"}</span>,
                },
              ]}
              rowKey={(r) => `${r.metric}-${r.year}`}
              size="small"
              pagination={false}
              bordered={false}
              rowClassName={() => "terminal-table-row"}
            />
          </Card>
        </>
      )}

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: "#e5e7eb", fontSize: 13 }}>同行对比</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>同业倍数参考</Text>
      </div>
      <Card size="small" title="同行对比" style={cardStyle} styles={{ body: { padding: "8px 16px" } }}>
        <Table<StockValuationPeer>
          dataSource={detail?.peer_summary.peers ?? []}
          columns={peerColumns}
          rowKey={(record) => record.code}
          size="small"
          pagination={false}
          scroll={{ x: "max-content" }}
          bordered={false}
          rowClassName={() => "terminal-table-row"}
        />
      </Card>
    </div>
  );
}
