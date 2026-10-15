import { Row, Col, Tag, Card, Table, Space } from "antd";
import { RocketOutlined } from "@ant-design/icons";
import { useMacroAllData, useCustomsTradeData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";
import type { CustomsCommodityProfile } from "../../types/stock";

const EXPORTS_IMPORTS_FIELDS = (c: ThemeColors) => [
  { key: "EXPORTS_SAME", label: "出口同比", color: c.primary, unit: "%" },
  { key: "IMPORTS_SAME", label: "进口同比", color: c.accent, unit: "%" },
];

const BALANCE_FIELDS = (c: ThemeColors) => [
  { key: "BALANCE", label: "贸易差额", color: c.accent, precision: 1 },
];

export default function TradeTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();
  const { data: customsData } = useCustomsTradeData();

  const exportsImports = data?.trade?.exports_imports;
  const balance = data?.trade?.balance;

  const exportYoY = exportsImports?.latest?.EXPORTS_SAME != null ? Number(exportsImports.latest.EXPORTS_SAME) : null;
  const importYoY = exportsImports?.latest?.IMPORTS_SAME != null ? Number(exportsImports.latest.IMPORTS_SAME) : null;
  const tradeBal = balance?.latest?.BALANCE != null ? Number(balance.latest.BALANCE) : null;

  const profiles = customsData?.matched_commodity_profiles ?? [];

  const commodityColumns = [
    {
      title: "出海 / 进口商品类别",
      key: "commodity",
      render: (_: unknown, record: CustomsCommodityProfile) => (
        <div>
          <div style={{ fontWeight: 600 }}>{record.commodity}</div>
          <div style={{ fontSize: 12, color: c.textSecondary }}>
            <Tag color={record.trade_type === "出口" ? "blue" : "purple"}>{record.trade_type}</Tag>
            <span>{record.category} · {record.unit}</span>
          </div>
        </div>
      ),
    },
    {
      title: "参考市场 / 来源地（静态）",
      dataIndex: "key_target_markets",
      key: "key_target_markets",
      render: (m: string) => <span style={{ fontSize: 12 }}>{m}</span>,
    },
    {
      title: "关联公司（静态，非受益判断）",
      dataIndex: "related_a_stocks",
      key: "related_a_stocks",
      render: (stocks: string[]) => (
        <Space size={[0, 4]} wrap>
          {stocks.map((stk) => (
            <Tag key={stk} color="cyan" style={{ fontSize: 12 }}>
              {stk}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: "商品说明（静态）",
      dataIndex: "description",
      key: "description",
      render: (desc: string) => <span style={{ fontSize: 12, color: c.textSecondary }}>{desc}</span>,
    },
  ];

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无进出口数据"
      errorTitle="进出口数据加载失败"
      minHeight={280}
    >
      {exportYoY != null ? (
        <div className="macro-insight-banner">
          <div className="macro-insight-banner__title">
            <span>💡 进出口与外贸景气度监测</span>
            <Tag color={tradeBal != null && tradeBal >= 0 ? "blue" : "purple"}>
              {tradeBal != null && tradeBal >= 0 ? "对外贸易顺差格局" : "外贸进出口动态"}
            </Tag>
          </div>
          <div className="macro-insight-banner__body">
            出口同比 <strong>{exportYoY > 0 ? `+${exportYoY.toFixed(1)}` : exportYoY.toFixed(1)}%</strong>，进口同比 <strong>{importYoY != null ? `${importYoY > 0 ? "+" : ""}${importYoY.toFixed(1)}%` : "-"}</strong>
            {tradeBal != null ? <>，当期贸易差额 <strong className="financial-num">{tradeBal.toFixed(1)}</strong> 亿美元</> : null}。
            外贸作为总需求“三驾马车”的重要组成部分，直观反映外需景气与全球供应链分工地位。
          </div>
        </div>
      ) : null}

      <Row className="macro-card-grid" gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="进出口同比增速"
            latest={exportsImports?.latest ?? null}
            trend={exportsImports?.trend ?? []}
            metadata={exportsImports}
            fields={EXPORTS_IMPORTS_FIELDS(c)}
          />
        </Col>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="贸易差额"
            latest={balance?.latest ?? null}
            trend={balance?.trend ?? []}
            metadata={balance}
            fields={BALANCE_FIELDS(c)}
          />
        </Col>
      </Row>

      <p style={{ color: c.textSecondary }}>
        海关数值仅为全国进出口总量；下方商品介绍、参考市场和公司映射不是当期海关统计，不含细分商品数量、金额、价格或目的地序列。
      </p>
      {/* 静态研究线索，不是细分商品量价 */}
      {profiles.length > 0 ? (
        <Card
          title={<span><RocketOutlined style={{ marginRight: 6, color: c.primary }} />重点商品与关联公司参考（静态资料）</span>}
          size="small"
          variant="borderless"
        >
          <Table
            rowKey="commodity"
            dataSource={profiles}
            columns={commodityColumns}
            pagination={false}
            size="middle"
            scroll={{ x: 800 }}
          />
        </Card>
      ) : null}
    </SectionDataState>
  );
}
