import { Row, Col, Tag } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

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

export default function RatesTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const lpr = data?.rates?.lpr;
  const shibor = data?.rates?.shibor;

  const lpr1y = lpr?.latest?.LPR1Y != null ? Number(lpr.latest.LPR1Y) : null;
  const lpr5y = lpr?.latest?.LPR5Y != null ? Number(lpr.latest.LPR5Y) : null;
  const termSpread = lpr1y != null && lpr5y != null ? Number((lpr5y - lpr1y).toFixed(2)) : null;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无利率数据"
      errorTitle="利率数据加载失败"
      minHeight={280}
    >
      {termSpread != null ? (
        <div className="macro-insight-banner">
          <div className="macro-insight-banner__title">
            <span>💡 政策基准与市场资金利率观察</span>
            <Tag color="geekblue">LPR 期限利差: {termSpread}%</Tag>
          </div>
          <div className="macro-insight-banner__body">
            1年期 LPR <strong>{lpr1y?.toFixed(2)}%</strong>，5年期以上 LPR <strong>{lpr5y?.toFixed(2)}%</strong>（利差 <strong className="financial-num">{termSpread}%</strong>）。
            1年期主要影响实体经济与企业短期流动性贷款，5年期以上主要锚定中长期制造业投资与房贷利率基准。
          </div>
        </div>
      ) : null}

      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="LPR 贷款市场报价利率"
            latest={lpr?.latest ?? null}
            trend={lpr?.trend ?? []}
            metadata={lpr}
            fields={LPR_FIELDS(c)}
          />
        </Col>
        <Col xs={24} md={12}>
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
