import { Button, Card, Col, Row, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { DownloadOutlined } from "@ant-design/icons";
import PreloadLink from "../../../components/PreloadLink";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import { formatNumberWithSeparators } from "../../../utils/format";
import { buildStockProfileUrl } from "../../../utils/stockLinks";
import type { NationalTeamPortrait, NationalTeamTopHolding } from "../../../types/stock";
import { downloadPortraitCsv } from "../utils/download";

const { Text } = Typography;

export default function NationalTeamPortraitPanel({ portrait }: { portrait?: NationalTeamPortrait }) {
  const isMobile = useMediaQuery("(max-width: 640px)");
  const p = portrait;
  if (!p) return null;

  const topHoldingsColumns: ColumnsType<NationalTeamTopHolding> = [
    {
      title: "排名",
      key: "rank",
      width: 55,
      align: "center",
      render: (_, __, index) => (
        <span
          className={`national-team-rotation__rank national-team-portrait__rank ${index < 3 ? `national-team-rotation__rank--${index + 1}` : ""}`}
        >
          {index + 1}
        </span>
      ),
    },
    {
      title: "标的",
      key: "stock",
      width: isMobile ? 130 : 180,
      render: (_, item) => (
        <div className="national-team-portrait__stock-col">
          <PreloadLink
            to={buildStockProfileUrl(item.code)}
            className="national-team-code national-team-code-link national-team-portrait__stock-name"
          >
            {item.name}
          </PreloadLink>
          <span className="national-team-portrait__stock-code">
            {item.code}
          </span>
        </div>
      ),
    },
    {
      title: "持股主体",
      dataIndex: "holder_name",
      key: "holder_name",
      width: isMobile ? 95 : 130,
      render: (val: string) => (
        <Tag color="blue" className="national-team-portrait__tag">
          {val}
        </Tag>
      ),
    },
    {
      title: "行业板块",
      dataIndex: "industry",
      key: "industry",
      width: isMobile ? 85 : 120,
      render: (val: string) => (
        <Tag color="cyan" className="national-team-portrait__tag">
          {val}
        </Tag>
      ),
    },
    {
      title: "占总股本比",
      dataIndex: "shareholding_ratio_pct",
      key: "shareholding_ratio_pct",
      width: isMobile ? 90 : 110,
      align: "right",
      render: (val: number) => (
        <strong className="national-team-portrait__ratio-val">
          {val.toFixed(2)}%
        </strong>
      ),
    },
    {
      title: "持股市值 (参考)",
      dataIndex: "market_value_100m",
      key: "market_value_100m",
      width: isMobile ? 105 : 140,
      align: "right",
      render: (val: number) => (
        <span className="national-team-portrait__mv-val">
          {formatNumberWithSeparators(Math.round(val))} 亿元
        </span>
      ),
    },
  ];

  return (
    <div className="national-team-portrait-panel" data-testid="national-team-portrait-panel">
      <div
        data-testid="national-team-portrait-reference"
        className="national-team-portrait__reference"
      >
        <Tag color={p.is_static ? "default" : "blue"} className="national-team-portrait__tag">
          {p.is_static ? "静态参考" : "动态数据"} · 截至 {p.as_of || p.reporting_period}
        </Tag>
        {p.source && (
          <Text type="secondary" className="national-team-portrait__source">
            来源：{p.source}
          </Text>
        )}
      </div>

      {/* 实体概览 */}
      <div className="national-team-portrait__entities-wrap">
        <Row gutter={[10, 10]}>
          {(p.entities ?? []).map((entity) => (
            <Col xs={24} md={8} key={entity.short_name}>
              <Card
                size="small"
                className="national-team-entity-card"
                title={
                  <div className="national-team-portrait__entity-header">
                    <span className="national-team-portrait__entity-name">{entity.short_name}</span>
                    <Tag color="purple" className="national-team-portrait__tag">
                      预估规模约 {entity.estimated_aum_trillion} 万亿
                    </Tag>
                  </div>
                }
              >
                <div className="national-team-portrait__entity-role">
                  <Text strong>职能定位：</Text>{entity.role}
                </div>
                <div className="national-team-portrait__entity-focus">
                  <Text strong>配置核心：</Text>{entity.focus}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 行业配置分布 */}
      <Card
        size="small"
        className="national-team-industry-card national-team-portrait__card"
        title={
          <div className="national-team-portrait__card-title-row">
            <span className="national-team-portrait__card-title">国家队战略底仓行业配置与权重分布</span>
            <span className="national-team-portrait__meta-text">
              披露口径：{p.reporting_period} · 总市值约 {p.total_market_value_trillion} 万亿元
            </span>
          </div>
        }
      >
        <Row gutter={[12, 12]}>
          {(p.industry_allocations ?? []).map((alloc) => {
            const barFillStyle = { width: `${Math.min(100, alloc.weight_pct * 2)}%` };
            return (
              <Col xs={24} sm={12} md={8} key={alloc.industry}>
                <div className="national-team-portrait__alloc-card">
                  <div className="national-team-portrait__alloc-header">
                    <span className="national-team-portrait__alloc-industry">{alloc.industry}</span>
                    <strong className="national-team-portrait__alloc-weight">
                      {alloc.weight_pct}%
                    </strong>
                  </div>
                  <div className="national-team-portrait__bar-track">
                    <div
                      className="national-team-portrait__bar-fill"
                      style={barFillStyle}
                    />
                  </div>
                  <div className="national-team-portrait__alloc-mv-row">
                    <span>持股市值约</span>
                    <span className="national-team-portrait__mono-val">{formatNumberWithSeparators(Math.round(alloc.market_value_100m))} 亿元</span>
                  </div>
                  <div className="national-team-portrait__tags-row">
                    {(alloc.representative_stocks ?? []).map((stock) => (
                      <Tag key={stock} className="national-team-portrait__stock-tag">
                        {stock}
                      </Tag>
                    ))}
                  </div>
                </div>
              </Col>
            );
          })}
        </Row>
      </Card>

      {/* 十大核心重仓股 */}
      <Card
        size="small"
        className="national-team-top-holdings-card"
        title={
          <div className="national-team-portrait__card-title-row">
            <span className="national-team-portrait__card-title">核心压舱石标的 · 汇金 / 证金 / 社保前十大战略重仓</span>
            <Text type="secondary" className="national-team-portrait__meta-text">
              上市企业定期报告十大股东口径
            </Text>
          </div>
        }
        extra={
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => {
              downloadPortraitCsv(p);
              message.success("已导出国家队战略底仓画像全景数据");
            }}
          >
            导出画像 CSV
          </Button>
        }
      >
        <Table<NationalTeamTopHolding>
          rowKey="code"
          size="small"
          columns={topHoldingsColumns}
          dataSource={p.top_holdings}
          pagination={false}
          scroll={{ x: 600 }}
        />
      </Card>
    </div>
  );
}
