import { Row, Col, Tag } from "antd";
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
            <span>💡 CPI - PPI 物价剪刀差研判</span>
            <Tag color={scissorsGap >= 0 ? "blue" : "orange"}>
              {scissorsGap >= 0 ? "剪刀差为正（中下游毛利偏好）" : "剪刀差为负（上游成本挤压）"}
            </Tag>
          </div>
          <div className="macro-insight-banner__body">
            当前最新 CPI 同比 <strong>{cpiYoY?.toFixed(2)}%</strong>，PPI 同比 <strong>{ppiYoY?.toFixed(2)}%</strong>，剪刀差为 <strong className="financial-num">{scissorsGap > 0 ? `+${scissorsGap}` : scissorsGap}%</strong>。
            {scissorsGap >= 0
              ? " 终端消费物价增速高于工业出厂价格，中下游制造业及消费行业成本传导顺畅、毛利率修复动能相对较强。"
              : " 上游工业品价格涨幅偏高或降幅小于终端，中下游企业成本端面临一定挤压。"}
          </div>
        </div>
      ) : null}

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
