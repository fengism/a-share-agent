import { ScheduleOutlined } from "@ant-design/icons";
import { Alert, Col, Row, Switch } from "antd";
import { useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function ScheduledTasksConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  isDirty,
  onReset,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();

  const dailyReviewEnabled = form.daily_review_prewarm_enabled ?? false;
  const macroAnalysisEnabled = form.macro_analysis_prewarm_enabled ?? false;
  const potentialStockEnabled = form.potential_stock_daily_enabled ?? false;
  const stockValuationEnabled = form.stock_valuation_snapshot_refresh_enabled ?? false;

  return (
    <SettingsCard
      title="定时与后台常驻任务"
      icon={<ScheduleOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存后台任务设置"
      onSave={onSave}
      isSaving={isSaving}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Alert
        type="info"
        showIcon
        title="后台常驻任务默认保持关闭"
        description="开启后任务将在系统后台按设定周期自动运行并可能消耗系统算力及大模型 API Token。"
        style={{ marginBottom: 20 }}
      />

      <Row gutter={[24, 20]}>
        <Col xs={24} md={12}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={fieldLabelStyle}>每日复盘自动预热</div>
              <div style={{ color: "var(--c-text-muted)", fontSize: "var(--c-font-xs)", marginTop: 4 }}>
                交易日收盘后自动调用大模型生成当日市场复盘，用户打开页面时可直接秒级查看。
              </div>
            </div>
            <Switch
              aria-label="每日复盘自动预热开关"
              checked={dailyReviewEnabled}
              onChange={(checked) => onChange({ daily_review_prewarm_enabled: checked })}
              checkedChildren="开启"
              unCheckedChildren="关闭"
            />
          </div>
        </Col>

        <Col xs={24} md={12}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={fieldLabelStyle}>宏观分析自动预热</div>
              <div style={{ color: "var(--c-text-muted)", fontSize: "var(--c-font-xs)", marginTop: 4 }}>
                定期在后台聚合全球宏观经济指标与新闻事件，自动驱动大模型生成宏观解读快照。
              </div>
            </div>
            <Switch
              aria-label="宏观分析自动预热开关"
              checked={macroAnalysisEnabled}
              onChange={(checked) => onChange({ macro_analysis_prewarm_enabled: checked })}
              checkedChildren="开启"
              unCheckedChildren="关闭"
            />
          </div>
        </Col>

        <Col xs={24} md={12}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={fieldLabelStyle}>潜在牛股每日扫描</div>
              <div style={{ color: "var(--c-text-muted)", fontSize: "var(--c-font-xs)", marginTop: 4 }}>
                交易日收盘后自动运行潜在牛股量化挖掘模型，扫描符合形态与资金特征的标的。
              </div>
            </div>
            <Switch
              aria-label="潜在牛股每日扫描开关"
              checked={potentialStockEnabled}
              onChange={(checked) => onChange({ potential_stock_daily_enabled: checked })}
              checkedChildren="开启"
              unCheckedChildren="关闭"
            />
          </div>
        </Col>

        <Col xs={24} md={12}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={fieldLabelStyle}>股票估值快照自动刷新</div>
              <div style={{ color: "var(--c-text-muted)", fontSize: "var(--c-font-xs)", marginTop: 4 }}>
                定时在后台预热自选股与持仓股票的最新估值指标，提升图表与估值看板加载速度。
              </div>
            </div>
            <Switch
              aria-label="股票估值快照自动刷新开关"
              checked={stockValuationEnabled}
              onChange={(checked) => onChange({ stock_valuation_snapshot_refresh_enabled: checked })}
              checkedChildren="开启"
              unCheckedChildren="关闭"
            />
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
