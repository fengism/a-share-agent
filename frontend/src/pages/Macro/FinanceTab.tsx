import { Row, Col, Tag, Card, Statistic } from "antd";
import { BankOutlined, FallOutlined, FundProjectionScreenOutlined, RiseOutlined } from "@ant-design/icons";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const MONEY_SUPPLY_FIELDS = (c: ThemeColors) => [
  { key: "BASIC_CURRENCY", label: "M2", color: c.primary, precision: 2, valueDivisor: 10_000 },
  { key: "CURRENCY", label: "M1", color: c.accent, precision: 2, valueDivisor: 10_000 },
  { key: "FREE_CASH", label: "M0", color: c.accent, precision: 2, valueDivisor: 10_000 },
];

const SOCIAL_FIN_FIELDS = (c: ThemeColors) => [
  { key: "SOCIAL_FINANCING_INCREMENT", label: "社融增量", color: c.primary, unit: "亿元", precision: 0 },
  { key: "RMB_LOAN", label: "人民币贷款", color: c.accent, unit: "亿元", precision: 0 },
  { key: "GOVERNMENT_BOND", label: "政府债券", color: c.up, unit: "亿元", precision: 0 },
  { key: "CORPORATE_BOND", label: "企业债券", color: c.warning, unit: "亿元", precision: 0 },
];

const LPR_FIELDS = (c: ThemeColors) => [
  { key: "LPR1Y", label: "1年期", color: c.primary, unit: "%" },
  { key: "LPR5Y", label: "5年期", color: c.accent, unit: "%" },
];

const SHIBOR_FIELDS = (c: ThemeColors) => [
  { key: "MONTH3", label: "3月", color: c.primary },
  { key: "MONTH6", label: "6月", color: c.accent },
  { key: "MONTH9", label: "9月", color: c.accent },
  { key: "YEAR1", label: "1年", color: c.down },
];

export default function FinanceTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const moneySupply = data?.monetary?.money_supply;
  const socialFin = data?.monetary?.social_financing;
  const lpr = data?.rates?.lpr;
  const shibor = data?.rates?.shibor;

  const m2 = moneySupply?.latest?.BASIC_CURRENCY != null ? (Number(moneySupply.latest.BASIC_CURRENCY) / 10_000).toFixed(2) : null;
  const lpr1y = lpr?.latest?.LPR1Y != null ? Number(lpr.latest.LPR1Y) : null;
  const lpr5y = lpr?.latest?.LPR5Y != null ? Number(lpr.latest.LPR5Y) : null;
  const termSpread = lpr1y != null && lpr5y != null ? Number((lpr5y - lpr1y).toFixed(2)) : null;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无金融货币数据"
      errorTitle="金融数据加载失败"
      minHeight={280}
    >
      <div className="macro-insight-banner">
        <div className="macro-insight-banner__title">
          <span>💡 宏观金融与货币流动性环境总览</span>
          <Tag color="cyan">M2 流动性池 + 政策基准利率</Tag>
        </div>
        <div className="macro-insight-banner__body">
          广义货币 M2 总量 <strong>{m2 ?? "-"} 万亿元</strong>
          {termSpread != null ? <>，1Y LPR <strong>{lpr1y?.toFixed(2)}%</strong> / 5Y LPR <strong>{lpr5y?.toFixed(2)}%</strong>（期限利差 <strong className="financial-num">{termSpread}%</strong>）</> : null}。
          全社会流动性总水闸保持适度充裕，长短期贷款市场利率处于历史极低水平，为实体经济与权益资产估值提供坚实的资金面护城河。
        </div>
      </div>

      {/* 4 大核心流动性 KPI 速览 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 14, marginBottom: 16 }}>
        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>广义货币 M2 总量</span>
            <Tag color="blue" icon={<FundProjectionScreenOutlined />}>流动性水池</Tag>
          </div>
          <Statistic
            value={m2 ?? "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: c.primary, marginTop: 4 } }}
            suffix={<span style={{ fontSize: 13, color: c.textMuted }}>万亿元</span>}
          />
          <div className="macro-kpi-subtext">实体经济与金融市场流动性底座</div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>1年期 LPR (短端贷款)</span>
            <Tag color="green" icon={<BankOutlined />}>企业融资基准</Tag>
          </div>
          <Statistic
            value={lpr1y != null ? `${lpr1y.toFixed(2)}%` : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: c.up, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">实体流动资金与日常借贷成本锚</div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>5年期以上 LPR (长端贷款)</span>
            <Tag color="cyan" icon={<FallOutlined />}>房贷与制造业</Tag>
          </div>
          <Statistic
            value={lpr5y != null ? `${lpr5y.toFixed(2)}%` : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: c.accent, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">个人按揭与中长期资本开支基准</div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>LPR 期限利差 (5Y - 1Y)</span>
            <Tag color="purple" icon={<RiseOutlined />}>曲线坡度</Tag>
          </div>
          <Statistic
            value={termSpread != null ? `${termSpread.toFixed(2)}%` : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: "#722ed1", marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">期限利差平缓，长期资金成本优势突出</div>
        </Card>
      </div>

      <div className="macro-section-divider"><span>💰 货币供应量与信用派生</span></div>
      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="货币供应量 M0/M1/M2（万亿元）"
            latest={moneySupply?.latest ?? null}
            trend={moneySupply?.trend ?? []}
            metadata={moneySupply}
            fields={MONEY_SUPPLY_FIELDS(c)}
          />
        </Col>
        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="社会融资规模"
            latest={socialFin?.latest ?? null}
            trend={socialFin?.trend ?? []}
            metadata={socialFin}
            fields={SOCIAL_FIN_FIELDS(c)}
          />
        </Col>
      </Row>

      <div className="macro-section-divider"><span>🏦 政策基准与市场资金利率</span></div>
      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="LPR 贷款市场报价利率"
            latest={lpr?.latest ?? null}
            trend={lpr?.trend ?? []}
            metadata={lpr}
            fields={LPR_FIELDS(c)}
          />
        </Col>
        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="SHIBOR 上海银行间同业拆放利率"
            latest={shibor?.latest ?? null}
            trend={shibor?.trend ?? []}
            metadata={shibor}
            fields={SHIBOR_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
