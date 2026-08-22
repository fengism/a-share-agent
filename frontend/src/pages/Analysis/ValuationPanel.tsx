import { useCallback, useMemo } from "react";
import { Card, Col, Row, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useValuationDetail } from "../../api/queries";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import AnalysisDimensionSummary from "./AnalysisDimensionSummary";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import type { AnalysisResult, DCFValuationResult, InstitutionForecast, StockValuationPeer, ValuationMethodResult } from "../../types/stock";
import { useColors, useStyles, useTokens, semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";

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

function percentileTag(value: number | null | undefined, tagStyle: React.CSSProperties) {
  if (value == null) return <Text type="secondary">-</Text>;
  if (value < 30) return <Tag style={{ ...tagStyle, ...semanticTagStyle("down") }}>偏低 {value.toFixed(1)}%</Tag>;
  if (value <= 70) return <Tag style={{ ...tagStyle, ...semanticTagStyle("warning") }}>中位 {value.toFixed(1)}%</Tag>;
  return <Tag style={{ ...tagStyle, ...semanticTagStyle("up") }}>偏高 {value.toFixed(1)}%</Tag>;
}

function valuationViewTag(value: string | null | undefined, tagStyle: React.CSSProperties) {
  if (!value) return <Text type="secondary">-</Text>;
  const tone: SemanticTagColor = value === "低估" ? "down" : value === "高估" ? "up" : "info";
  return <Tag style={{ ...tagStyle, ...semanticTagStyle(tone) }}>{value}</Tag>;
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

function formatTableNumber(value: number | null | undefined) {
  return value != null ? value.toFixed(2) : "-";
}

function forecastMetricLabel(value: string) {
  if (value === "EPS") return "每股收益";
  if (value === "NET_PROFIT") return "净利润";
  return value;
}

function renderMethodCard(title: string, item: ValuationMethodResult | DCFValuationResult | undefined, c: ReturnType<typeof useColors>, tagStyle: React.CSSProperties, t: ReturnType<typeof useTokens>) {
  const tileStyle = {
    padding: `${t.space[4]} ${t.space[5]}`,
    background: c.hoverBg,
    border: `1px solid ${c.border}`,
    borderRadius: t.radius.lg,
    textAlign: "center" as const,
  };
  return (
    <div style={tileStyle}>
      <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>{title}</div>
      <div style={{ fontSize: t.font["2xl"], fontWeight: Number(t.weight.bold), color: c.textPrimary, lineHeight: t.leading.tight, letterSpacing: 0.1, marginBottom: t.space[2] }}>
        {item?.available ? `¥${item.per_share_value?.toFixed(2) ?? "-"}` : "不可用"}
      </div>
      <Paragraph style={{ margin: 0, fontSize: t.font.sm, color: c.textSecondary }}>
        {item?.available ? `区间 ${formatPriceRange(item.value_range)}` : (item?.reason ?? "-")}
      </Paragraph>
      <div style={{ display: "flex", justifyContent: "center", gap: t.space[2], flexWrap: "wrap", marginTop: t.space[2] }}>
        <Tag style={{ ...tagStyle, ...semanticTagStyle("primary"), marginBottom: 0 }}>权重 {formatWeight(item?.weight)}</Tag>
        <Tag style={{ ...tagStyle, ...semanticTagStyle("accent"), marginBottom: 0 }}>置信 {formatConfidence(item?.confidence_score)}</Tag>
      </div>
      <Paragraph style={{ margin: `${t.space[2]} 0 0`, fontSize: t.font.sm, color: c.textSecondary }}>
        {item?.available ? `相对现价 ${formatPercent(item.upside_pct)}` : item?.applicability}
      </Paragraph>
      {item?.applicability && item.available && (
        <Paragraph style={{ margin: `${t.space[2]} 0 0`, fontSize: t.font.sm, color: c.textSecondary }}>
          {item.applicability}
        </Paragraph>
      )}
      {item?.basis && (
        <Paragraph style={{ margin: `${t.space[2]} 0 0`, fontSize: t.font.sm, color: c.textSecondary }}>
          {item.basis}
        </Paragraph>
      )}
    </div>
  );
}

export default function ValuationPanel({ code, analysis }: Props) {
  const c = useColors();
  const t = useTokens();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const { cardStyle, sectionHeaderStyle, tagStyle, sectionCardBodyStyle, metricTileStyle, metricValueEmphasisStyle } = useStyles();
  const { data: detail, isLoading, error, refetch } = useValuationDetail(code);

  const forecastColumns: ColumnsType<InstitutionForecast> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "指标",
          key: "metric-year",
          width: 150,
          render: (_: unknown, record: InstitutionForecast) => (
            <div>
              <Tag style={{ ...tagStyle, marginBottom: t.space[1] }}>{forecastMetricLabel(record.metric)}</Tag>
              <div style={{ color: c.textMuted, fontSize: t.font.xs }}>{record.year}</div>
            </div>
          ),
        },
        {
          title: <span style={{ color: c.accent }}>均值</span>,
          dataIndex: "mean_value",
          key: "mean_value",
          width: 88,
          align: "right",
          render: (value: number | null) => <span style={{ fontSize: t.font.md, fontWeight: Number(t.weight.semibold), color: c.accent }}>{formatTableNumber(value)}</span>,
        },
      ];
    }

    return [
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>指标</span>,
        dataIndex: "metric",
        key: "metric",
        render: (value: string) => <Tag style={tagStyle}>{forecastMetricLabel(value)}</Tag>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>年度</span>,
        dataIndex: "year",
        key: "year",
        render: (value: string) => <span style={{ fontSize: t.font.sm, color: c.textPrimary }}>{value}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>机构数</span>,
        dataIndex: "institution_count",
        key: "institution_count",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.primary }}>{value ?? "-"}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>最小值</span>,
        dataIndex: "min_value",
        key: "min_value",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{formatTableNumber(value)}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.accent }}>均值</span>,
        dataIndex: "mean_value",
        key: "mean_value",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.md, fontWeight: Number(t.weight.semibold), color: c.accent }}>{formatTableNumber(value)}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>最大值</span>,
        dataIndex: "max_value",
        key: "max_value",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{formatTableNumber(value)}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>行业均值</span>,
        dataIndex: "industry_avg",
        key: "industry_avg",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{formatTableNumber(value)}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>单位</span>,
        dataIndex: "unit",
        key: "unit",
        render: (value: string | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{value ?? "-"}</span>,
      },
    ];
  }, [c, isNarrow, tagStyle, t]);

  const peerColumns: ColumnsType<StockValuationPeer> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "同行",
          key: "peer",
          width: 150,
          render: (_: unknown, record: StockValuationPeer) => (
            <div>
              <div style={{ color: c.textPrimary, fontSize: t.font.sm, fontWeight: Number(t.weight.semibold) }}>{record.name}</div>
              <div style={{ color: c.textMuted, fontSize: t.font.xs }}>{record.code}</div>
            </div>
          ),
        },
        {
          title: "PE(TTM)",
          dataIndex: "pe_ttm",
          key: "pe_ttm",
          width: 92,
          align: "right",
          render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{formatTableNumber(value)}</span>,
        },
      ];
    }

    return [
      { title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>名称</span>, dataIndex: "name", key: "name", render: (value: string) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{value}</span> },
      { title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>代码</span>, dataIndex: "code", key: "code", render: (value: string) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{value}</span> },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>PE(TTM)</span>,
        dataIndex: "pe_ttm",
        key: "pe_ttm",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{formatTableNumber(value)}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>PB</span>,
        dataIndex: "pb",
        key: "pb",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{formatTableNumber(value)}</span>,
      },
      {
        title: <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: c.textSecondary }}>PS(TTM)</span>,
        dataIndex: "ps_ttm",
        key: "ps_ttm",
        align: "right",
        render: (value: number | null) => <span style={{ fontSize: t.font.sm, color: c.textSecondary }}>{formatTableNumber(value)}</span>,
      },
    ];
  }, [c, isNarrow, t]);

  const renderForecastExpandedRow = useCallback((record: InstitutionForecast) => (
    <ResponsiveMetricGrid
      items={[
        { key: "institutions", label: "机构数", value: record.institution_count ?? "-" },
        { key: "min", label: "最小值", value: formatTableNumber(record.min_value) },
        { key: "max", label: "最大值", value: formatTableNumber(record.max_value) },
        { key: "industry", label: "行业均值", value: formatTableNumber(record.industry_avg) },
        { key: "unit", label: "单位", value: record.unit ?? "-" },
      ]}
    />
  ), []);

  const renderPeerExpandedRow = useCallback((record: StockValuationPeer) => (
    <ResponsiveMetricGrid
      items={[
        { key: "pb", label: "PB", value: formatTableNumber(record.pb) },
        { key: "ps", label: "PS(TTM)", value: formatTableNumber(record.ps_ttm) },
      ]}
    />
  ), []);

  return (
    <SectionDataState
      isLoading={isLoading}
      error={error}
      onRetry={() => refetch()}
      errorTitle="估值数据加载失败"
      skeletonRows={7}
      minHeight={320}
    >
      <div style={{ display: "grid", gap: t.space[4] }}>
      <Card
        size="small"
        className="analysis-dimension-card"
        style={{ ...cardStyle, borderTop: `3px solid ${c.primary}55` }}
      >
        <AnalysisDimensionSummary label="估值面" score={analysis?.overall_rating}>
          <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>当前估值快照</Text>
          <div className="analysis-dimension-summary__metrics">
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>PE(TTM)</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.pe_ttm?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: t.space[2] }}>{percentileTag(detail?.percentiles.pe_3y, { ...tagStyle, margin: 0 })}</div>
            </div>
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>PB</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.pb?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: t.space[2] }}>{percentileTag(detail?.percentiles.pb_3y, { ...tagStyle, margin: 0 })}</div>
            </div>
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>PS(TTM)</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.ps_ttm?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: t.space[2] }}>{percentileTag(detail?.percentiles.ps_3y, { ...tagStyle, margin: 0 })}</div>
            </div>
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>PEG</div>
              <div style={metricValueEmphasisStyle}>{detail?.multiples.peg?.toFixed(2) ?? "-"}</div>
              <div style={{ marginTop: t.space[2], color: c.textSecondary, fontSize: t.font.sm }}>成长匹配度</div>
            </div>
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>股票画像</div>
              <div style={{ ...metricValueEmphasisStyle, fontSize: t.font.xl }}>{detail?.profile?.label ?? "-"}</div>
              <div style={{ marginTop: t.space[2] }}>{valuationViewTag(detail?.valuation_view, { ...tagStyle, margin: 0 })}</div>
            </div>
          </div>
        </AnalysisDimensionSummary>
      </Card>

      <Card size="small" title="动态估值结论" style={{ ...cardStyle, marginBottom: t.space[4] }} styles={{ body: { ...sectionCardBodyStyle, padding: `${t.space[4]} ${t.space[5]}` } }}>
        <Row gutter={[t.space[4], t.space[4]]}>
          <Col xs={24} md={8}>
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>合理估值区间</div>
              <div style={{ ...metricValueEmphasisStyle, fontSize: t.font.xl }}>{formatPriceRange(detail?.fair_value_range)}</div>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>加权中枢</div>
              <div style={{ ...metricValueEmphasisStyle, fontSize: t.font.xl }}>{detail?.blended_fair_value != null ? `¥${detail.blended_fair_value.toFixed(2)}` : "-"}</div>
            </div>
          </Col>
          <Col xs={24} md={8}>
            <div style={metricTileStyle}>
              <div style={{ color: c.textSecondary, fontSize: t.font.sm, marginBottom: t.space[1] }}>方法权重</div>
              <div style={{ display: "flex", gap: t.space[2], justifyContent: "center", flexWrap: "wrap" }}>
                {Object.entries(detail?.method_weights ?? {}).map(([method, weight]) => (
                  <Tag key={method} style={{ ...tagStyle, marginBottom: 0 }}>{method.toUpperCase()} {formatWeight(weight)}</Tag>
                ))}
              </div>
            </div>
          </Col>
        </Row>
        {detail?.valuation_summary && (
          <Paragraph style={{ margin: `${t.space[4]} 0 0`, color: c.textSecondary }}>{detail.valuation_summary}</Paragraph>
        )}
      </Card>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>估值方法对比</Text>
        <Text type="secondary" style={{ fontSize: t.font.sm }}>PE / PB / PS / PEG / DCF</Text>
      </div>
      <Card size="small" title="五种估值结果" style={{ ...cardStyle, marginBottom: t.space[4] }} styles={{ body: { ...sectionCardBodyStyle, padding: `${t.space[4]} ${t.space[5]}` } }}>
        <Row gutter={[t.space[4], t.space[4]]}>
          <Col xs={24} md={8}>{renderMethodCard("PE 估值法", detail?.fair_values.pe as ValuationMethodResult | undefined, c, tagStyle, t)}</Col>
          <Col xs={24} md={8}>{renderMethodCard("PB 估值法", detail?.fair_values.pb as ValuationMethodResult | undefined, c, tagStyle, t)}</Col>
          <Col xs={24} md={8}>{renderMethodCard("PS 估值法", detail?.fair_values.ps as ValuationMethodResult | undefined, c, tagStyle, t)}</Col>
          <Col xs={24} md={8}>{renderMethodCard("PEG 估值法", detail?.fair_values.peg as ValuationMethodResult | undefined, c, tagStyle, t)}</Col>
          <Col xs={24} md={8}>{renderMethodCard("DCF 估值法", detail?.fair_values.dcf as DCFValuationResult | undefined, c, tagStyle, t)}</Col>
        </Row>
      </Card>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>财务基础与关键假设</Text>
        <Text type="secondary" style={{ fontSize: t.font.sm }}>估值参数参考</Text>
      </div>
      <Card size="small" title="关键假设与财务基础" style={{ ...cardStyle, marginBottom: t.space[4] }} styles={{ body: { ...sectionCardBodyStyle, padding: `${t.space[4]} ${t.space[5]}` } }}>
        <Row gutter={[t.space[4], t.space[4]]}>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: c.textSecondary, fontSize: t.font.sm }}>营收</div><div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.semibold) }}>{formatAmount(detail?.fundamentals.revenue)}</div></div></Col>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: c.textSecondary, fontSize: t.font.sm }}>净利润</div><div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.semibold) }}>{formatAmount(detail?.fundamentals.net_profit)}</div></div></Col>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: c.textSecondary, fontSize: t.font.sm }}>股东权益</div><div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.semibold) }}>{formatAmount(detail?.fundamentals.shareholders_equity)}</div></div></Col>
          <Col xs={24} md={6}><div style={metricTileStyle}><div style={{ color: c.textSecondary, fontSize: t.font.sm }}>经营现金流</div><div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.semibold) }}>{formatAmount(detail?.fundamentals.operating_cashflow)}</div></div></Col>
        </Row>
        <Row gutter={[t.space[4], t.space[4]]} style={{ marginTop: t.space[4] }}>
          <Col xs={24} md={8}><div style={metricTileStyle}><div style={{ color: c.textSecondary, fontSize: t.font.sm }}>营收同比</div><div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.semibold) }}>{formatPercent(detail?.fundamentals.revenue_yoy)}</div></div></Col>
          <Col xs={24} md={8}><div style={metricTileStyle}><div style={{ color: c.textSecondary, fontSize: t.font.sm }}>净利润同比</div><div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.semibold) }}>{formatPercent(detail?.fundamentals.net_profit_yoy)}</div></div></Col>
          <Col xs={24} md={8}><div style={metricTileStyle}><div style={{ color: c.textSecondary, fontSize: t.font.sm }}>扣非净利润同比</div><div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.semibold) }}>{formatPercent(detail?.fundamentals.non_net_profit_yoy)}</div></div></Col>
        </Row>
        {detail?.notes?.length ? (
          <div style={{ marginTop: t.space[4] }}>
            {detail.notes.map((note) => (
              <Paragraph key={note} style={{ marginBottom: t.space[2], color: c.textSecondary }}>{note}</Paragraph>
            ))}
          </div>
        ) : null}
      </Card>

      {detail?.institution_forecasts && detail.institution_forecasts.length > 0 && (
        <>
          <div style={sectionHeaderStyle}>
            <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>机构一致预期</Text>
            <Text type="secondary" style={{ fontSize: t.font.sm }}>EPS / 净利润预测</Text>
          </div>
          <Card
            size="small"
            title="机构一致预期"
            style={{ ...cardStyle, marginBottom: t.space[4] }}
            styles={{ body: { padding: isNarrow ? `${t.space[2]}` : `${t.space[2]} ${t.space[4]}` } }}
          >
            <Table<InstitutionForecast>
              dataSource={detail.institution_forecasts}
              columns={forecastColumns}
              rowKey={(r) => `${r.metric}-${r.year}`}
              size="small"
              pagination={false}
              expandable={isNarrow ? {
                expandedRowRender: renderForecastExpandedRow,
                columnWidth: 38,
              } : undefined}
              scroll={isNarrow ? undefined : { x: "max-content" }}
              bordered={false}
              rowClassName={() => "terminal-table-row"}
            />
          </Card>
        </>
      )}

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>同行对比</Text>
        <Text type="secondary" style={{ fontSize: t.font.sm }}>同业倍数参考</Text>
      </div>
      <Card
        size="small"
        title="同行对比"
        style={cardStyle}
        styles={{ body: { padding: isNarrow ? `${t.space[2]}` : `${t.space[2]} ${t.space[4]}` } }}
      >
        <Table<StockValuationPeer>
          dataSource={detail?.peer_summary.peers ?? []}
          columns={peerColumns}
          rowKey={(record) => record.code}
          size="small"
          pagination={false}
          expandable={isNarrow ? {
            expandedRowRender: renderPeerExpandedRow,
            columnWidth: 38,
          } : undefined}
          scroll={isNarrow ? undefined : { x: "max-content" }}
          bordered={false}
          rowClassName={() => "terminal-table-row"}
        />
      </Card>
      </div>
    </SectionDataState>
  );
}
