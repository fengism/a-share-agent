import { DatabaseOutlined } from "@ant-design/icons";
import { Col, InputNumber, Row } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "./SettingsCard";

/** 与后端 Settings.database_backup_retention_count 的默认值保持一致。 */
const DEFAULT_RETENTION_COUNT = 2;

export default function BackupRetentionCard({
  form,
  onChange,
  onSave,
  isSaving,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="数据库在线备份"
      icon={<DatabaseOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存备份份数"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[16, 16]}>
        <Col xs={12} md={8}>
          <div style={fieldLabelStyle}>备份保留份数</div>
          <InputNumber
            min={1}
            max={90}
            value={form.database_backup_retention_count ?? DEFAULT_RETENTION_COUNT}
            onChange={(value) =>
              onChange({ database_backup_retention_count: value ?? DEFAULT_RETENTION_COUNT })
            }
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24}>
          <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
            每天对 market / user / industry / market_daily 四个库各生成一份 gzip 压缩备份，
            超出份数的旧备份自动清理。market_daily 含10 年日线（约 8.5 GB），每多一份都会明显增加磁盘占用；
            保存后下一轮备份任务即生效，无需重启。
          </span>
        </Col>
      </Row>
    </SettingsCard>
  );
}