import { DatabaseOutlined } from "@ant-design/icons";
import { Col, InputNumber, Row, Switch } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "./SettingsCard";

/** 与后端 Settings 默认值保持一致。 */
const DEFAULT_RETENTION_COUNT = 3;
const DEFAULT_INCLUDE_MARKET_DAILY = true;
const DEFAULT_MARKET_DAILY_INTERVAL_DAYS = 7;
const DEFAULT_MARKET_DAILY_COMPRESSION_LEVEL = 1;

export default function BackupRetentionCard({
  form,
  onChange,
  onSave,
  isSaving,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  const includeMarketDaily =
    form.database_backup_include_market_daily ?? DEFAULT_INCLUDE_MARKET_DAILY;

  return (
    <SettingsCard
      title="数据库在线备份"
      icon={<DatabaseOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存备份配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <div style={fieldLabelStyle}>备份保留份数</div>
          <InputNumber
            aria-label="备份保留份数"
            min={1}
            max={90}
            value={form.database_backup_retention_count ?? DEFAULT_RETENTION_COUNT}
            onChange={(value) =>
              onChange({ database_backup_retention_count: value ?? DEFAULT_RETENTION_COUNT })
            }
            style={{ width: "100%" }}
          />
        </Col>

        <Col xs={12} md={6}>
          <div style={fieldLabelStyle}>日线大库备份</div>
          <div style={{ paddingTop: 4 }}>
            <Switch
              aria-label="日线大库备份开关"
              checked={includeMarketDaily}
              onChange={(checked) =>
                onChange({ database_backup_include_market_daily: checked })
              }
              checkedChildren="开启"
              unCheckedChildren="关闭"
            />
          </div>
        </Col>

        <Col xs={12} md={6}>
          <div style={fieldLabelStyle}>大库备份周期 (天)</div>
          <InputNumber
            aria-label="大库备份周期"
            min={1}
            max={90}
            addonAfter="天"
            disabled={!includeMarketDaily}
            value={form.market_daily_backup_interval_days ?? DEFAULT_MARKET_DAILY_INTERVAL_DAYS}
            onChange={(value) =>
              onChange({
                market_daily_backup_interval_days:
                  value ?? DEFAULT_MARKET_DAILY_INTERVAL_DAYS,
              })
            }
            style={{ width: "100%" }}
          />
        </Col>

        <Col xs={12} md={6}>
          <div style={fieldLabelStyle}>大库压缩级别 (1-9)</div>
          <InputNumber
            aria-label="大库压缩级别"
            min={1}
            max={9}
            addonAfter="级"
            disabled={!includeMarketDaily}
            value={form.market_daily_backup_compression_level ?? DEFAULT_MARKET_DAILY_COMPRESSION_LEVEL}
            onChange={(value) =>
              onChange({
                market_daily_backup_compression_level:
                  value ?? DEFAULT_MARKET_DAILY_COMPRESSION_LEVEL,
              })
            }
            style={{ width: "100%" }}
          />
        </Col>

        <Col span={24}>
          <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            基础库（market / user / auth / industry）体积较小，每日备份并保留指定份数；
            日线大库（market_daily，约 13GB+）可配置独立备份周期（默认 7 天 / 一周一次）与 gzip 压缩级别（推荐 1 级极速压缩，耗时短且对服务影响小；级别 9 压缩率高但极度耗 CPU）；
            保存后下一轮备份任务即生效，无需重启。
          </span>
        </Col>
      </Row>
    </SettingsCard>
  );
}