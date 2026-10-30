import { Row, Col, Tag, Card, Statistic } from "antd";
import { LineChartOutlined, ShopOutlined, AppstoreOutlined } from "@ant-design/icons";
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
  const mfgDiff = mfgPmi != null ? Number((mfgPmi - 50).toFixed(1)) : null;

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
            <span>💡 采购经理人指数（PMI）景气区间与工业传导研判</span>
            <Tag color={mfgPmi >= 50 ? "green" : "volcano"}>
              {mfgPmi >= 50 ? "制造业处于扩张区间 (≥50)" : "制造业处于收缩区间 (<50)"}
            </Tag>
          </div>
          <div className="macro-insight-banner__body">
            最新制造业 PMI 为 <strong>{mfgPmi.toFixed(1)}</strong>，非制造业 PMI 为 <strong>{nonMfgPmi != null ? nonMfgPmi.toFixed(1) : "-"}</strong>。
            50% 为实体经济强弱分水岭（荣枯线）。
            {mfgPmi >= 50
              ? " 表明制造业供需扩张动能恢复良好，通常领先工业企业盈利与中游装备制造补库周期 1~2 个季度。"
              : " 表明工业企业新订单与生产活动存在阶段性收缩压力，政策逆周期发力与财政货币协同支持预期增强。"}
          </div>
        </div>
      ) : null}

      {/* 3 大核心景气 KPI 速览 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14, marginBottom: 16 }}>
        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>制造业 PMI (最新)</span>
            <Tag color={(mfgPmi ?? 0) >= 50 ? "green" : "volcano"} icon={<LineChartOutlined />}>
              {(mfgPmi ?? 0) >= 50 ? "景气扩张" : "收缩承压"}
            </Tag>
          </div>
          <Statistic
            value={mfgPmi != null ? mfgPmi.toFixed(1) : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: (mfgPmi ?? 0) >= 50 ? c.up : c.down, marginTop: 4 } }}
            suffix={<span style={{ fontSize: 13, color: c.textMuted }}>/ 50荣枯线</span>}
          />
          <div className="macro-kpi-subtext">
            {mfgDiff != null ? (mfgDiff >= 0 ? `高于荣枯线 +${mfgDiff} 点` : `低于荣枯线 ${mfgDiff} 点`) : "荣枯分界线"}
          </div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>非制造业 PMI (商务活动)</span>
            <Tag color={(nonMfgPmi ?? 0) >= 50 ? "cyan" : "orange"} icon={<ShopOutlined />}>
              {(nonMfgPmi ?? 0) >= 50 ? "服务扩张" : "承压"}
            </Tag>
          </div>
          <Statistic
            value={nonMfgPmi != null ? nonMfgPmi.toFixed(1) : "-"}
            styles={{ content: { fontSize: 22, fontWeight: 700, color: (nonMfgPmi ?? 0) >= 50 ? c.accent : c.warning, marginTop: 4 } }}
            suffix={<span style={{ fontSize: 13, color: c.textMuted }}>/ 50荣枯线</span>}
          />
          <div className="macro-kpi-subtext">
            涵盖现代服务业与建筑业实物施工景气
          </div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>综合经济动能评估</span>
            <Tag color="purple" icon={<AppstoreOutlined />}>实体定调</Tag>
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, color: c.textPrimary, marginTop: 8 }}>
            {(mfgPmi ?? 0) >= 50 && (nonMfgPmi ?? 0) >= 50
              ? "双轮协同扩张"
              : (mfgPmi ?? 0) >= 50
              ? "工业生产领跑，内需待提振"
              : (nonMfgPmi ?? 0) >= 50
              ? "服务业支撑底盘，制造业承压"
              : "实体周期筑底，政策发力期"}
          </div>
          <div className="macro-kpi-subtext" style={{ marginTop: 6 }}>
            国家统计局官方采购经理人联合指数
          </div>
        </Card>
      </div>

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
