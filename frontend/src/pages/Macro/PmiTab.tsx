import { Row, Col, Tag } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const PMI_FIELDS = (c: ThemeColors) => [
  { key: "MAKE_INDEX", label: "制造业 PMI", color: c.primary, precision: 1 },
  { key: "NMAKE_INDEX", label: "非制造业 PMI", color: c.accent, precision: 1 },
];

export default function PmiTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const pmi = data?.sentiment?.pmi;
  const mfgPmi = pmi?.latest?.MAKE_INDEX != null ? Number(pmi.latest.MAKE_INDEX) : null;
  const nonMfgPmi = pmi?.latest?.NMAKE_INDEX != null ? Number(pmi.latest.NMAKE_INDEX) : null;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无 PMI 数据"
      errorTitle="PMI 数据加载失败"
      minHeight={280}
    >
      {mfgPmi != null ? (
        <div className="macro-insight-banner">
          <div className="macro-insight-banner__title">
            <span>💡 采购经理人指数（PMI）景气区间研判</span>
            <Tag color={mfgPmi >= 50 ? "green" : "volcano"}>
              {mfgPmi >= 50 ? "制造业处于扩张区间 (≥50)" : "制造业处于收缩区间 (<50)"}
            </Tag>
          </div>
          <div className="macro-insight-banner__body">
            最新制造业 PMI 为 <strong>{mfgPmi.toFixed(1)}</strong>，非制造业 PMI 为 <strong>{nonMfgPmi != null ? nonMfgPmi.toFixed(1) : "-"}</strong>。
            50% 为经济强弱分界线（荣枯线），{mfgPmi >= 50 ? "表明制造业经济总体处于扩张发展态势。" : "表明制造业生产与市场需求阶段性承压，需关注宏观逆周期托底政策。"}
          </div>
        </div>
      ) : null}

      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24}>
          <MacroIndicatorCard
            title="PMI 采购经理人指数"
            latest={pmi?.latest ?? null}
            trend={pmi?.trend ?? []}
            metadata={pmi}
            fields={PMI_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
