import { ApiOutlined } from "@ant-design/icons";
import { Col, Input, InputNumber, Row, Switch } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function BotConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  isDirty,
  onReset,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="飞书 Bot Command（全局）"
      icon={<ApiOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Bot 配置"
      onSave={onSave}
      isSaving={isSaving}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Row gutter={[24, 16]}>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>启用 Bot</div>
          <Switch
            checked={form.bot_enabled ?? false}
            onChange={(value) => onChange({ bot_enabled: value })}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>服务账号 ID</div>
          <InputNumber
            min={0}
            value={form.bot_service_user_id ?? 0}
            onChange={(value) => onChange({ bot_service_user_id: value ?? 0 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>命令前缀</div>
          <Input
            value={form.bot_command_prefix || "/"}
            onChange={(event) => onChange({ bot_command_prefix: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Bot 飞书 App ID</div>
          <Input
            value={form.bot_feishu_app_id || ""}
            onChange={(event) => onChange({ bot_feishu_app_id: event.target.value })}
            placeholder="cli_xxxxx"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Bot 飞书 App Secret</div>
          <Input.Password
            value={form.bot_feishu_app_secret || ""}
            onChange={(event) => onChange({ bot_feishu_app_secret: event.target.value })}
            placeholder="输入新的 Secret 以覆盖"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Verification Token</div>
          <Input.Password
            value={form.feishu_verification_token || ""}
            onChange={(event) => onChange({ feishu_verification_token: event.target.value })}
            placeholder="飞书事件订阅 Verification Token"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Encrypt Key</div>
          <Input.Password
            value={form.feishu_encrypt_key || ""}
            onChange={(event) => onChange({ feishu_encrypt_key: event.target.value })}
            placeholder="飞书事件订阅 Encrypt Key"
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>限流次数</div>
          <InputNumber
            min={1}
            max={1000}
            value={form.bot_rate_limit_requests ?? 10}
            onChange={(value) => onChange({ bot_rate_limit_requests: value ?? 10 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>限流窗口（秒）</div>
          <InputNumber
            min={1}
            max={86400}
            value={form.bot_rate_limit_window ?? 60}
            onChange={(value) => onChange({ bot_rate_limit_window: value ?? 60 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>签名允许偏差（秒）</div>
          <InputNumber
            min={1}
            max={3600}
            value={form.bot_webhook_max_skew_seconds ?? 300}
            onChange={(value) => onChange({ bot_webhook_max_skew_seconds: value ?? 300 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>事件去重保留（秒）</div>
          <InputNumber
            min={1}
            max={604800}
            value={form.bot_event_dedup_ttl_seconds ?? 600}
            onChange={(value) => onChange({ bot_event_dedup_ttl_seconds: value ?? 600 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>任务轮询间隔（秒）</div>
          <InputNumber
            min={0.1}
            max={60}
            step={0.1}
            value={form.bot_job_poll_seconds ?? 1}
            onChange={(value) => onChange({ bot_job_poll_seconds: value ?? 1 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>Worker 并发</div>
          <InputNumber
            min={1}
            max={8}
            value={form.bot_job_worker_concurrency ?? 2}
            onChange={(value) => onChange({ bot_job_worker_concurrency: value ?? 2 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>批量分析并发</div>
          <InputNumber
            min={1}
            max={8}
            value={form.bot_batch_concurrency ?? 2}
            onChange={(value) => onChange({ bot_batch_concurrency: value ?? 2 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>批量最大股票数</div>
          <InputNumber
            min={1}
            max={50}
            value={form.bot_batch_max_stocks ?? 10}
            onChange={(value) => onChange({ bot_batch_max_stocks: value ?? 10 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>任务最大尝试次数</div>
          <InputNumber
            min={1}
            max={20}
            value={form.bot_job_max_attempts ?? 3}
            onChange={(value) => onChange({ bot_job_max_attempts: value ?? 3 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>任务租约（秒）</div>
          <InputNumber
            min={30}
            max={86400}
            value={form.bot_job_lease_seconds ?? 900}
            onChange={(value) => onChange({ bot_job_lease_seconds: value ?? 900 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>失败重试基数（秒）</div>
          <InputNumber
            min={0}
            max={3600}
            value={form.bot_job_retry_base_seconds ?? 5}
            onChange={(value) => onChange({ bot_job_retry_base_seconds: value ?? 5 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>Bot 管理员飞书用户 ID（每行一个）</div>
          <Input.TextArea
            rows={3}
            value={(form.bot_admin_users ?? []).join("\n")}
            onChange={(event) => onChange({ bot_admin_users: event.target.value.split("\n") })}
            placeholder={"ou_xxxxx\nou_yyyyy"}
          />
          <div style={{ marginTop: 4, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            `/batch` 等敏感命令仅允许该名单内用户执行。Worker 并发变更需重启后端生效。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
