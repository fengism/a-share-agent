import { useState, useEffect, useCallback } from "react";
import {
  Card,
  Select,
  Input,
  Slider,
  Switch,
  Button,
  Typography,
  message,
  Row,
  Col,
  Divider,
} from "antd";
import {
  SaveOutlined,
  RobotOutlined,
  SendOutlined,
  BookOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useConfig, useUpdateConfig } from "../../api/queries";
import type { ConfigUpdate, ProviderDefault } from "../../types/settings";
import {
  pageContainerStyle,
  pageHeaderStyle,
  pageTitleStyle,
  pageDescriptionStyle,
  cardStyle,
  fieldLabelStyle,
  sectionCardBodyStyle,
  darkColors,
} from "../../styles/ui";

const { Text } = Typography;

const PROVIDER_OPTIONS = [
  { value: "deepseek", label: "DeepSeek" },
  { value: "qwen", label: "通义千问 (Qwen)" },
  { value: "openai", label: "OpenAI" },
  { value: "zhipu", label: "智谱 (GLM)" },
  { value: "claude", label: "Claude (litellm)" },
];

export default function SettingsPage() {
  const { data: config, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();

  const [form, setForm] = useState<ConfigUpdate>({});
  const [initialized, setInitialized] = useState(false);
  const [prevProvider, setPrevProvider] = useState<string>("");

  useEffect(() => {
    if (!config || initialized) return;
    setInitialized(true);
    setForm({
        llm_provider: config.llm_provider,
        llm_api_key: config.llm_api_key,
        llm_base_url: config.llm_base_url,
        llm_model: config.llm_model,
        llm_temperature: config.llm_temperature,
        feishu_enabled: config.feishu_enabled,
        feishu_app_id: config.feishu_app_id,
        feishu_app_secret: config.feishu_app_secret,
        feishu_folder_token: config.feishu_folder_token,
        feishu_wiki_space_id: config.feishu_wiki_space_id,
        feishu_wiki_daily_review_parent: config.feishu_wiki_daily_review_parent,
        feishu_wiki_analysis_parent: config.feishu_wiki_analysis_parent,
        feishu_daily_review_folder: config.feishu_daily_review_folder,
        feishu_analysis_folder: config.feishu_analysis_folder,
        feishu_default_receiver: config.feishu_default_receiver,
        notion_enabled: config.notion_enabled,
        notion_parent_page_id: config.notion_parent_page_id,
        notion_database_id: config.notion_database_id,
        iwencai_enabled: config.iwencai_enabled,
        iwencai_base_url: config.iwencai_base_url,
        iwencai_api_key: config.iwencai_api_key,
      });
      setPrevProvider(config.llm_provider);
  }, [config, initialized]);

  const set = useCallback((patch: ConfigUpdate) => {
    setForm((prev) => ({ ...prev, ...patch }));
  }, []);

  const handleProviderChange = useCallback(
    (newProvider: string) => {
      const defaults = config?.provider_defaults?.[newProvider] as
        | ProviderDefault
        | undefined;
      const oldDefaults = config?.provider_defaults?.[prevProvider] as
        | ProviderDefault
        | undefined;

      const patch: ConfigUpdate = { llm_provider: newProvider };

      // Auto-fill base_url/model if they still match old provider defaults
      if (defaults) {
        if (
          !form.llm_base_url ||
          form.llm_base_url === oldDefaults?.base_url
        ) {
          patch.llm_base_url = defaults.base_url;
        }
        if (!form.llm_model || form.llm_model === oldDefaults?.model) {
          patch.llm_model = defaults.model;
        }
      }

      set(patch);
      setPrevProvider(newProvider);
    },
    [config, form.llm_base_url, form.llm_model, prevProvider, set],
  );

  const handleSaveLLM = useCallback(() => {
    const patch: ConfigUpdate = {
      llm_provider: form.llm_provider,
      llm_base_url: form.llm_base_url,
      llm_model: form.llm_model,
      llm_temperature: form.llm_temperature,
    };
    // Only send api_key if user actually changed it (not the masked value)
    if (
      form.llm_api_key &&
      !form.llm_api_key.endsWith("***")
    ) {
      patch.llm_api_key = form.llm_api_key;
    }
    updateConfig.mutate(patch, {
      onSuccess: () => {
        message.success("大模型配置已保存");
      },
      onError: (err: Error) => {
        message.error(`保存失败: ${err.message}`);
      },
    });
  }, [form, updateConfig]);

  const handleSaveFeishu = useCallback(() => {
    const patch: ConfigUpdate = {
      feishu_enabled: form.feishu_enabled,
      feishu_app_id: form.feishu_app_id,
      feishu_folder_token: form.feishu_folder_token,
      feishu_wiki_space_id: form.feishu_wiki_space_id,
      feishu_wiki_daily_review_parent: form.feishu_wiki_daily_review_parent,
      feishu_wiki_analysis_parent: form.feishu_wiki_analysis_parent,
      feishu_daily_review_folder: form.feishu_daily_review_folder,
      feishu_analysis_folder: form.feishu_analysis_folder,
      feishu_default_receiver: form.feishu_default_receiver,
    };
    if (
      form.feishu_app_secret &&
      !form.feishu_app_secret.endsWith("***")
    ) {
      patch.feishu_app_secret = form.feishu_app_secret;
    }
    updateConfig.mutate(patch, {
      onSuccess: () => {
        message.success("飞书配置已保存");
      },
      onError: (err: Error) => {
        message.error(`保存失败: ${err.message}`);
      },
    });
  }, [form, updateConfig]);

  const handleSaveNotion = useCallback(() => {
    updateConfig.mutate(
      {
        notion_enabled: form.notion_enabled,
        notion_parent_page_id: form.notion_parent_page_id,
        notion_database_id: form.notion_database_id,
      },
      {
        onSuccess: () => {
          message.success("Notion 配置已保存");
        },
        onError: (err: Error) => {
          message.error(`保存失败: ${err.message}`);
        },
      },
    );
  }, [form, updateConfig]);

  const handleSaveIwencai = useCallback(() => {
    const patch: ConfigUpdate = {
      iwencai_enabled: form.iwencai_enabled,
      iwencai_base_url: form.iwencai_base_url,
    };
    if (
      form.iwencai_api_key &&
      !form.iwencai_api_key.endsWith("***")
    ) {
      patch.iwencai_api_key = form.iwencai_api_key;
    }
    updateConfig.mutate(patch, {
      onSuccess: () => {
        message.success("问财数据源配置已保存");
      },
      onError: (err: Error) => {
        message.error(`保存失败: ${err.message}`);
      },
    });
  }, [form, updateConfig]);

  if (isLoading) {
    return (
      <div
        style={{
          ...pageContainerStyle,
          color: darkColors.textSecondary,
          textAlign: "center",
          paddingTop: 80,
        }}
      >
        加载配置中...
      </div>
    );
  }

  if (!config) {
    return (
      <div
        style={{
          ...pageContainerStyle,
          color: darkColors.up,
          textAlign: "center",
          paddingTop: 80,
        }}
      >
        配置加载失败，请确认后端服务已启动。
        <div style={{ marginTop: 12, color: darkColors.textMuted, fontSize: 12 }}>
          API 地址: /api/config
        </div>
      </div>
    );
  }

  return (
    <div style={pageContainerStyle}>
      {/* Header */}
      <div style={pageHeaderStyle}>
        <h2 style={pageTitleStyle}>
          <RobotOutlined style={{ marginRight: 8 }} />
          系统配置
        </h2>
        <p style={pageDescriptionStyle}>
          配置大模型、飞书推送、问财数据源和 Notion 转存参数，修改后即时生效无需重启。
        </p>
      </div>

      {/* LLM Config */}
      <Card
        title={
          <span>
            <RobotOutlined style={{ marginRight: 8 }} />
            大模型配置
          </span>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <Row gutter={[24, 16]}>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>Provider</div>
            <Select
              value={form.llm_provider}
              onChange={handleProviderChange}
              options={PROVIDER_OPTIONS}
              style={{ width: "100%" }}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>API Key</div>
            <Input.Password
              value={form.llm_api_key || ""}
              onChange={(e) => set({ llm_api_key: e.target.value })}
              placeholder="输入新的 API Key 以覆盖"
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>Base URL</div>
            <Input
              value={form.llm_base_url || ""}
              onChange={(e) => set({ llm_base_url: e.target.value })}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>Model</div>
            <Input
              value={form.llm_model || ""}
              onChange={(e) => set({ llm_model: e.target.value })}
            />
          </Col>
          <Col span={24}>
            <div style={fieldLabelStyle}>
              Temperature: {form.llm_temperature ?? 0.1}
            </div>
            <Slider
              min={0}
              max={1}
              step={0.05}
              value={form.llm_temperature ?? 0.1}
              onChange={(v) => set({ llm_temperature: v })}
            />
          </Col>
        </Row>
        <Divider style={{ borderColor: darkColors.border, margin: "16px 0" }} />
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveLLM}
          loading={updateConfig.isPending}
        >
          保存大模型配置
        </Button>
      </Card>

      {/* Feishu Config */}
      <Card
        title={
          <span>
            <SendOutlined style={{ marginRight: 8 }} />
            飞书推送配置
          </span>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <Row gutter={[24, 16]}>
          <Col span={24}>
            <div style={fieldLabelStyle}>启用飞书推送</div>
            <Switch
              checked={form.feishu_enabled ?? true}
              onChange={(v) => set({ feishu_enabled: v })}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>App ID</div>
            <Input
              value={form.feishu_app_id || ""}
              onChange={(e) => set({ feishu_app_id: e.target.value })}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>App Secret</div>
            <Input.Password
              value={form.feishu_app_secret || ""}
              onChange={(e) => set({ feishu_app_secret: e.target.value })}
              placeholder="输入新的 Secret 以覆盖"
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>默认文档目录 Token</div>
            <Input
              value={form.feishu_folder_token || ""}
              onChange={(e) => set({ feishu_folder_token: e.target.value })}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>Wiki 空间 ID（优先于文档目录）</div>
            <Input
              value={form.feishu_wiki_space_id || ""}
              onChange={(e) => set({ feishu_wiki_space_id: e.target.value })}
              placeholder="填写后文档将推送到知识库"
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>复盘 Wiki 父节点 Token</div>
            <Input
              value={form.feishu_wiki_daily_review_parent || ""}
              onChange={(e) => set({ feishu_wiki_daily_review_parent: e.target.value })}
              placeholder="复盘文档挂载到此节点下"
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>分析 Wiki 父节点 Token</div>
            <Input
              value={form.feishu_wiki_analysis_parent || ""}
              onChange={(e) => set({ feishu_wiki_analysis_parent: e.target.value })}
              placeholder="分析文档挂载到此节点下"
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>复盘文档目录 Token</div>
            <Input
              value={form.feishu_daily_review_folder || ""}
              onChange={(e) =>
                set({ feishu_daily_review_folder: e.target.value })
              }
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>分析文档目录 Token</div>
            <Input
              value={form.feishu_analysis_folder || ""}
              onChange={(e) =>
                set({ feishu_analysis_folder: e.target.value })
              }
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>默认接收人 (open_id / chat_id)</div>
            <Input
              value={form.feishu_default_receiver || ""}
              onChange={(e) =>
                set({ feishu_default_receiver: e.target.value })
              }
            />
          </Col>
        </Row>
        <Divider style={{ borderColor: darkColors.border, margin: "16px 0" }} />
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveFeishu}
          loading={updateConfig.isPending}
        >
          保存飞书配置
        </Button>
      </Card>

      {/* Notion Config */}
      <Card
        title={
          <span>
            <BookOutlined style={{ marginRight: 8 }} />
            Notion 转存配置
          </span>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <Row gutter={[24, 16]}>
          <Col span={24}>
            <div style={fieldLabelStyle}>启用 Notion 转存</div>
            <Switch
              checked={form.notion_enabled ?? false}
              onChange={(v) => set({ notion_enabled: v })}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>Parent Page ID</div>
            <Input
              value={form.notion_parent_page_id || ""}
              onChange={(e) =>
                set({ notion_parent_page_id: e.target.value })
              }
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>Database ID</div>
            <Input
              value={form.notion_database_id || ""}
              onChange={(e) =>
                set({ notion_database_id: e.target.value })
              }
            />
          </Col>
        </Row>
        <Divider style={{ borderColor: darkColors.border, margin: "16px 0" }} />
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveNotion}
          loading={updateConfig.isPending}
        >
          保存 Notion 配置
        </Button>
      </Card>

      {/* Iwencai Config */}
      <Card
        title={
          <span>
            <SearchOutlined style={{ marginRight: 8 }} />
            问财数据源配置
          </span>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <Row gutter={[24, 16]}>
          <Col span={24}>
            <div style={fieldLabelStyle}>启用问财数据源</div>
            <Switch
              checked={form.iwencai_enabled ?? false}
              onChange={(v) => set({ iwencai_enabled: v })}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>Base URL</div>
            <Input
              value={form.iwencai_base_url || ""}
              onChange={(e) => set({ iwencai_base_url: e.target.value })}
            />
          </Col>
          <Col span={24} sm={12}>
            <div style={fieldLabelStyle}>API Key</div>
            <Input.Password
              value={form.iwencai_api_key || ""}
              onChange={(e) => set({ iwencai_api_key: e.target.value })}
              placeholder="输入新的 API Key 以覆盖"
            />
          </Col>
        </Row>
        <Divider style={{ borderColor: darkColors.border, margin: "16px 0" }} />
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveIwencai}
          loading={updateConfig.isPending}
        >
          保存问财配置
        </Button>
      </Card>

      {/* Provider Defaults Reference */}
      <Card
        title="Provider 默认值参考"
        style={cardStyle}
        styles={{ body: sectionCardBodyStyle }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 12,
          }}
        >
          {Object.entries(config.provider_defaults || {}).map(
            ([name, defaults]) => (
              <div
                key={name}
                style={{
                  padding: "10px 14px",
                  background: darkColors.elevatedBg,
                  border: `1px solid ${darkColors.border}`,
                  borderRadius: 8,
                  fontSize: 12,
                }}
              >
                <Text strong style={{ color: darkColors.primary, fontSize: 13 }}>
                  {PROVIDER_OPTIONS.find((p) => p.value === name)?.label || name}
                </Text>
                <div style={{ marginTop: 6, color: darkColors.textSecondary }}>
                  <div>URL: {defaults.base_url}</div>
                  <div>Model: {defaults.model}</div>
                </div>
              </div>
            ),
          )}
        </div>
      </Card>
    </div>
  );
}
