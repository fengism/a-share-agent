import type { ReactNode } from "react";
import { ApiOutlined, BookOutlined, RobotOutlined, SaveOutlined, SearchOutlined, SendOutlined } from "@ant-design/icons";
import { Button, Card, Col, Divider, Input, InputNumber, Row, Select, Slider, Switch, Typography } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import type { ConfigUpdate, LlmApiMode, ProviderDefault } from "../../types/settings";

const { Text } = Typography;

const API_MODE_OPTIONS: Array<{ value: LlmApiMode; label: string }> = [
  { value: "auto", label: "自动（跟随 Provider）" },
  { value: "openai", label: "OpenAI Compatible" },
  { value: "litellm", label: "LiteLLM" },
];

const API_MODE_LABELS: Record<LlmApiMode, string> = Object.fromEntries(
  API_MODE_OPTIONS.map((option) => [option.value, option.label]),
) as Record<LlmApiMode, string>;

interface ConfigCardProps {
  form: ConfigUpdate;
  onChange: (patch: ConfigUpdate) => void;
  onSave: () => void;
  isSaving: boolean;
}

interface SettingsCardProps {
  title: string;
  icon: ReactNode;
  saveLabel: string;
  onSave: () => void;
  isSaving: boolean;
  children: ReactNode;
}

function SettingsCard({ title, icon, saveLabel, onSave, isSaving, children }: SettingsCardProps) {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();

  return (
    <Card
      title={<span>{icon}{title}</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      {children}
      <Divider style={{ borderColor: colors.border, margin: "16px 0" }} />
      <Button type="primary" icon={<SaveOutlined />} onClick={onSave} loading={isSaving}>
        {saveLabel}
      </Button>
    </Card>
  );
}

export function LlmConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  onProviderChange,
  providerDefaults,
}: ConfigCardProps & {
  onProviderChange: (provider: string) => void;
  providerDefaults: Record<string, ProviderDefault>;
}) {
  const { fieldLabelStyle } = useStyles();
  const selectedDefaults = form.llm_provider ? providerDefaults[form.llm_provider] : undefined;
  const providerOptions = Object.entries(providerDefaults).map(([value, defaults]) => ({
    value,
    label: defaults.label || value,
  }));

  return (
    <SettingsCard
      title="大模型配置"
      icon={<RobotOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存大模型配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Provider</div>
          <Select value={form.llm_provider} onChange={onProviderChange} options={providerOptions} style={{ width: "100%" }} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API 模式</div>
          <Select<LlmApiMode>
            value={form.llm_api_mode || "auto"}
            onChange={(value) => onChange({ llm_api_mode: value })}
            options={API_MODE_OPTIONS}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>
            API Key{selectedDefaults && !selectedDefaults.api_key_required ? "（可选）" : ""}
          </div>
          <Input.Password
            value={form.llm_api_key || ""}
            onChange={(event) => onChange({ llm_api_key: event.target.value })}
            placeholder={selectedDefaults?.api_key_required === false ? "本地服务可留空" : "输入新的 API Key 以覆盖"}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API Version（可选）</div>
          <Input
            value={form.llm_api_version || ""}
            onChange={(event) => onChange({ llm_api_version: event.target.value })}
            placeholder={selectedDefaults?.api_version || "Azure 等接口需要"}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Base URL</div>
          <Input value={form.llm_base_url || ""} onChange={(event) => onChange({ llm_base_url: event.target.value })} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Model</div>
          <Input value={form.llm_model || ""} onChange={(event) => onChange({ llm_model: event.target.value })} />
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>Temperature: {form.llm_temperature ?? 0.1}</div>
          <Slider
            min={0}
            max={1}
            step={0.05}
            value={form.llm_temperature ?? 0.1}
            onChange={(value) => onChange({ llm_temperature: value })}
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}

export function FeishuConfigCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();

  return (
    <SettingsCard
      title="飞书推送配置"
      icon={<SendOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存飞书配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>启用飞书推送</div>
          <Switch checked={form.feishu_enabled ?? true} onChange={(value) => onChange({ feishu_enabled: value })} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>App ID</div>
          <Input value={form.feishu_app_id || ""} onChange={(event) => onChange({ feishu_app_id: event.target.value })} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>App Secret</div>
          <Input.Password
            value={form.feishu_app_secret || ""}
            onChange={(event) => onChange({ feishu_app_secret: event.target.value })}
            placeholder="输入新的 Secret 以覆盖"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>默认文档目录 Token</div>
          <Input value={form.feishu_folder_token || ""} onChange={(event) => onChange({ feishu_folder_token: event.target.value })} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Wiki 空间 ID（优先于文档目录）</div>
          <Input
            value={form.feishu_wiki_space_id || ""}
            onChange={(event) => onChange({ feishu_wiki_space_id: event.target.value })}
            placeholder="填写后文档将推送到知识库"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>复盘 Wiki 父节点 Token</div>
          <Input
            value={form.feishu_wiki_daily_review_parent || ""}
            onChange={(event) => onChange({ feishu_wiki_daily_review_parent: event.target.value })}
            placeholder="复盘文档挂载到此节点下"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>分析 Wiki 父节点 Token</div>
          <Input
            value={form.feishu_wiki_analysis_parent || ""}
            onChange={(event) => onChange({ feishu_wiki_analysis_parent: event.target.value })}
            placeholder="分析文档挂载到此节点下"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>复盘文档目录 Token</div>
          <Input
            value={form.feishu_daily_review_folder || ""}
            onChange={(event) => onChange({ feishu_daily_review_folder: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>分析文档目录 Token</div>
          <Input
            value={form.feishu_analysis_folder || ""}
            onChange={(event) => onChange({ feishu_analysis_folder: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>默认接收人 (open_id / chat_id)</div>
          <Input
            value={form.feishu_default_receiver || ""}
            onChange={(event) => onChange({ feishu_default_receiver: event.target.value })}
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}

export function NotionConfigCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();

  return (
    <SettingsCard
      title="Notion 转存配置"
      icon={<BookOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Notion 配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>启用 Notion 转存</div>
          <Switch checked={form.notion_enabled ?? false} onChange={(value) => onChange({ notion_enabled: value })} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Parent Page ID</div>
          <Input
            value={form.notion_parent_page_id || ""}
            onChange={(event) => onChange({ notion_parent_page_id: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Database ID</div>
          <Input
            value={form.notion_database_id || ""}
            onChange={(event) => onChange({ notion_database_id: event.target.value })}
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}

export function IwencaiConfigCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();

  return (
    <SettingsCard
      title="问财数据源配置"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存问财配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>启用问财数据源</div>
          <Switch checked={form.iwencai_enabled ?? false} onChange={(value) => onChange({ iwencai_enabled: value })} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Base URL</div>
          <Input value={form.iwencai_base_url || ""} onChange={(event) => onChange({ iwencai_base_url: event.target.value })} />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API Key</div>
          <Input.Password
            value={form.iwencai_api_key || ""}
            onChange={(event) => onChange({ iwencai_api_key: event.target.value })}
            placeholder="输入新的 API Key 以覆盖"
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}

export function TwitterConfigCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="Twitter 财经账号配置（全局）"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Twitter 配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>Twitter/X 财经账号列表（每行一个，不含 @）</div>
          <Input.TextArea
            rows={4}
            value={(form.twitter_feeds ?? []).join("\n")}
            onChange={(event) => onChange({ twitter_feeds: event.target.value.split("\n") })}
            placeholder={"qinbafrank\n账号2\n账号3"}
          />
          <div style={{ marginTop: 4, fontSize: 12, color: colors.textMuted }}>
            用于拉取 Twitter/X 上的财经推文和文章，每行填写一个账号名（不带 @）
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}

export function DataSourceCookiesCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="数据源 Cookie 配置（全局）"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存数据源 Cookie"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>东方财富 Cookie</div>
          <Input.Password
            value={form.eastmoney_cookie || ""}
            onChange={(event) => onChange({ eastmoney_cookie: event.target.value })}
            placeholder="留空使用内置默认值"
          />
          <div style={{ marginTop: 4, fontSize: 12, color: colors.textMuted }}>
            从浏览器 DevTools → Network → 请求头中复制 Cookie 值
          </div>
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>百度 Cookie</div>
          <Input.Password
            value={form.baidu_cookie || ""}
            onChange={(event) => onChange({ baidu_cookie: event.target.value })}
            placeholder="留空使用内置默认值"
          />
          <div style={{ marginTop: 4, fontSize: 12, color: colors.textMuted }}>
            从浏览器 DevTools → Network → 请求头中复制 Cookie 值
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}

export function BotConfigCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="飞书 Bot Command（全局）"
      icon={<ApiOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Bot 配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>启用 Bot</div>
          <Switch checked={form.bot_enabled ?? false} onChange={(value) => onChange({ bot_enabled: value })} />
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
          <div style={{ marginTop: 4, fontSize: 12, color: colors.textMuted }}>
            `/batch` 等敏感命令仅允许该名单内用户执行。Worker 并发变更需重启后端生效。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}

export function ProviderDefaultsCard({ providerDefaults }: { providerDefaults: Record<string, ProviderDefault> }) {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();

  return (
    <Card title="Provider 默认值参考" style={cardStyle} styles={{ body: sectionCardBodyStyle }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
        {Object.entries(providerDefaults).map(([name, defaults]) => (
          <div
            key={name}
            style={{
              padding: "10px 14px",
              background: colors.elevatedBg,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              fontSize: 12,
            }}
          >
            <Text strong style={{ color: colors.primary, fontSize: 13 }}>
              {defaults.label || name}
            </Text>
            <div style={{ marginTop: 4, color: colors.textMuted }}>{defaults.description}</div>
            <div style={{ marginTop: 6, color: colors.textSecondary, wordBreak: "break-all" }}>
              <div>模式: {API_MODE_LABELS[defaults.api_mode]}</div>
              <div>API Key: {defaults.api_key_required ? "必填" : "可选"}</div>
              <div>URL: {defaults.base_url}</div>
              <div>Model: {defaults.model}</div>
              {defaults.api_version && <div>API Version: {defaults.api_version}</div>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
