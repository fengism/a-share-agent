import { Row, Col, Tag, Card, Statistic } from "antd";
import { DollarOutlined, ShopOutlined, TransactionOutlined } from "@ant-design/icons";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const CPI_FIELDS = (c: ThemeColors) => [
  { key: "NATIONAL_SAME", label: "同比", color: c.up, unit: "%" },
  { key: "NATIONAL_SEQUENTIAL", label: "环比", color: c.accent, unit: "%" },
  { key: "NATIONAL_ACCUMULATE", label: "累计", color: c.primary, unit: "%" },
];

const PPI_FIELDS = (c: ThemeColors) => [
  { key: "BASE_SAME", label: "同比", color: c.up, unit: "%" },
  { key: "BASE_ACCUMULATE", label: "累计", color: c.primary, unit: "%" },
];

export default function PriceTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const cpi = data?.prices?.cpi;
  const ppi = data?.prices?.ppi;

  const cpiYoY = cpi?.latest?.NATIONAL_SAME != null ? Number(cpi.latest.NATIONAL_SAME) : null;
  const cpiMoM = cpi?.latest?.NATIONAL_SEQUENTIAL != null ? Number(cpi.latest.NATIONAL_SEQUENTIAL) : null;
  const ppiYoY = ppi?.latest?.BASE_SAME != null ? Number(ppi.latest.BASE_SAME) : null;
  const scissorsGap = cpiYoY != null && ppiYoY != null ? Number((cpiYoY - ppiYoY).toFixed(2)) : null;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无价格指标数据"
      errorTitle="宏观价格数据加载失败"
      minHeight={280}
    >
      {scissorsGap != null ? (
        <div className="macro-insight-banner">
          <div className="macro-insight-banner__title">
            <span>💡 CPI - PPI 工业与消费物价剪刀差研判</span>
            <Tag color={scissorsGap >= 0 ? "blue" : "orange"}>
              {scissorsGap >= 0 ? "剪刀差为正（中下游毛利偏好）" : "剪刀差为负（上游成本挤压）"}
            </Tag>
          </div>
          <div className="macro-insight-banner__body">
            当前最新 CPI 同比 <strong>{cpiYoY?.toFixed(2)}%</strong>，PPI 同比 <strong>{ppiYoY?.toFixed(2)}%</strong>，
            两者利润剪刀差为 <strong className="financial-num">{scissorsGap > 0 ? `+${scissorsGap}` : scissorsGap}%</strong>。
            {scissorsGap >= 0
              ? " 终端消费品售价增速高于工业出厂端原料价格，消费、食品饮料与中下游高端制造（家电、汽车）毛利率呈扩张态势。"
              : " 上游工业原材料价格偏强或终端提价能力受限，中下游制造业利润空间面临一定挤压。"}
          </div>
        </div>
      ) : null}

      {/* 3 大核心通胀与利润剪刀差 KPI 速览 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14, marginBottom: 16 }}>
        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>CPI 居民消费价格 (同比)</span>
            <Tag color="cyan" icon={<ShopOutlined />}>终端消费</Tag>
          </div>
          <Statistic
            value={cpiYoY != null ? `${cpiYoY > 0 ? "+" : ""}${cpiYoY.toFixed(2)}%` : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: (cpiYoY ?? 0) >= 0 ? c.up : c.down, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">
            环比: {cpiMoM != null ? `${cpiMoM > 0 ? "+" : ""}${cpiMoM.toFixed(2)}%` : "-"} · 终端物价温和
          </div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>PPI 工业出厂价格 (同比)</span>
            <Tag color="volcano" icon={<DollarOutlined />}>工业出厂</Tag>
          </div>
          <Statistic
            value={ppiYoY != null ? `${ppiYoY > 0 ? "+" : ""}${ppiYoY.toFixed(2)}%` : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: (ppiYoY ?? 0) >= 0 ? c.up : c.down, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">
            工业品出厂价格周期与企业营收弹性
          </div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>CPI - PPI 利润剪刀差</span>
            <Tag color={(scissorsGap ?? 0) >= 0 ? "blue" : "orange"} icon={<TransactionOutlined />}>
              {(scissorsGap ?? 0) >= 0 ? "中下游毛利改善" : "上游成本挤压"}
            </Tag>
          </div>
          <Statistic
            value={scissorsGap != null ? `${scissorsGap > 0 ? "+" : ""}${scissorsGap.toFixed(2)}%` : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: (scissorsGap ?? 0) >= 0 ? "#1677ff" : "#fa8c16", marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">
            {(scissorsGap ?? 0) >= 0 ? "中下游制造与消费品毛利更具韧性" : "关注上游资源品提价对中游的挤压"}
          </div>
        </Card>
      </div>

      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="CPI 居民消费价格指数"
            latest={cpi?.latest ?? null}
            trend={cpi?.trend ?? []}
            metadata={cpi}
            fields={CPI_FIELDS(c)}
          />
        </Col>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="PPI 工业生产者出厂价格指数"
            latest={ppi?.latest ?? null}
            trend={ppi?.trend ?? []}
            metadata={ppi}
            fields={PPI_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
