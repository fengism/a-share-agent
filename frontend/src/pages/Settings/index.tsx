import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
  Tag,
  Space,
  Popconfirm,
} from "antd";
import {
  SaveOutlined,
  RobotOutlined,
  SendOutlined,
  BookOutlined,
  SearchOutlined,
  TeamOutlined,
  PlusOutlined,
  CopyOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useConfig, useUpdateConfig, useInvites, useCreateInvite, useRevokeInvite } from "../../api/queries";
import type { ConfigUpdate, ProviderDefault } from "../../types/settings";
import type { InviteItem } from "../../types/auth";
import { useAuthStore } from "../../store/authStore";
import ChangePasswordCard from "../../components/ChangePasswordCard";
import { useStyles, useColors } from "../../styles/ui";

const { Text } = Typography;

const PROVIDER_OPTIONS = [
  { value: "deepseek", label: "DeepSeek" },
  { value: "qwen", label: "通义千问 (Qwen)" },
  { value: "openai", label: "OpenAI" },
  { value: "zhipu", label: "智谱 (GLM)" },
  { value: "claude", label: "Claude (litellm)" },
];

function InviteManagerCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const c = useColors();
  const queryClient = useQueryClient();
  const { data: invites = [], isLoading } = useInvites(true);
  const createInvite = useCreateInvite();
  const revokeInvite = useRevokeInvite();
  const [expiresInDays, setExpiresInDays] = useState<number | undefined>(undefined);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["invites"] });

  const handleGenerate = () => {
    createInvite.mutate(expiresInDays, {
      onSuccess: () => {
        refresh();
        message.success("已生成新的邀请码");
      },
      onError: (err: Error) => message.error(`生成失败: ${err.message}`),
    });
  };

  const handleRevoke = (code: string) => {
    revokeInvite.mutate(code, {
      onSuccess: () => {
        refresh();
        message.success("邀请码已撤销");
      },
      onError: (err: Error) => message.error(`撤销失败: ${err.message}`),
    });
  };

  const statusTag = (inv: InviteItem) => {
    if (inv.used) return <Tag color="default">已使用</Tag>;
    if (inv.expired) return <Tag color="red">已过期</Tag>;
    return <Tag color="green">未使用</Tag>;
  };

  const copyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      message.success("邀请码已复制");
    } catch {
      message.warning("复制失败，请手动选择复制");
    }
  };

  return (
    <Card
      title={<span><TeamOutlined style={{ marginRight: 8 }} />邀请码管理</span>}
      extra={
        <Space>
          <Select
            size="small"
            value={expiresInDays ?? 0}
            style={{ width: 128 }}
            onChange={(v) => setExpiresInDays(v === 0 ? undefined : v)}
            options={[
              { value: 0, label: "永不过期" },
              { value: 1, label: "1 天后过期" },
              { value: 7, label: "7 天后过期" },
              { value: 30, label: "30 天后过期" },
            ]}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleGenerate}
            loading={createInvite.isPending}
          >
            生成邀请码
          </Button>
        </Space>
      }
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ fontSize: 12, color: c.textMuted, marginBottom: 12 }}>
        新用户注册需填写有效且未使用的邀请码；每个邀请码仅可使用一次。可为邀请码设置过期时间，未使用的邀请码可随时撤销。
      </div>
      {isLoading ? (
        <div style={{ color: c.textSecondary }}>加载中...</div>
      ) : invites.length === 0 ? (
        <div style={{ color: c.textMuted }}>暂无邀请码，点击右上角生成。</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {invites.map((inv) => (
            <div
              key={inv.code}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                gap: 8, padding: "8px 12px", background: c.elevatedBg,
                border: `1px solid ${c.border}`, borderRadius: 8,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <code style={{ fontFamily: "monospace", fontSize: 13, color: c.textPrimary, wordBreak: "break-all" }}>
                  {inv.code}
                </code>
                <div style={{ fontSize: 11, color: c.textMuted, marginTop: 2 }}>
                  {inv.expires_at ? `过期时间：${inv.expires_at}` : "永不过期"}
                </div>
              </div>
              <Space>
                {statusTag(inv)}
                {!inv.used && (
                  <Button size="small" icon={<CopyOutlined />} onClick={() => copyCode(inv.code)}>
                    复制
                  </Button>
                )}
                {!inv.used && (
                  <Popconfirm
                    title="撤销该邀请码？"
                    description="撤销后将无法用于注册。"
                    okText="撤销"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => handleRevoke(inv.code)}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} loading={revokeInvite.isPending}>
                      撤销
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function SettingsPage() {
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle, cardStyle, fieldLabelStyle, sectionCardBodyStyle } = useStyles();
  const c = useColors();
  const { data: config, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();
  const queryClient = useQueryClient();
  const user = useAuthStore((st) => st.user);
  const isAdmin = !!config?.is_admin;

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
        twitter_feeds: config.twitter_feeds,
        eastmoney_cookie: config.eastmoney_cookie,
        baidu_cookie: config.baidu_cookie,
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
      onSuccess: (data) => {
        queryClient.setQueryData(["config"], data);
        message.success("大模型配置已保存");
      },
      onError: (err: Error) => {
        message.error(`保存失败: ${err.message}`);
      },
    });
  }, [form, updateConfig, queryClient]);

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
      onSuccess: (data) => {
        queryClient.setQueryData(["config"], data);
        message.success("飞书配置已保存");
      },
      onError: (err: Error) => {
        message.error(`保存失败: ${err.message}`);
      },
    });
  }, [form, updateConfig, queryClient]);

  const handleSaveNotion = useCallback(() => {
    updateConfig.mutate(
      {
        notion_enabled: form.notion_enabled,
        notion_parent_page_id: form.notion_parent_page_id,
        notion_database_id: form.notion_database_id,
      },
      {
        onSuccess: (data) => {
          queryClient.setQueryData(["config"], data);
          message.success("Notion 配置已保存");
        },
        onError: (err: Error) => {
          message.error(`保存失败: ${err.message}`);
        },
      },
    );
  }, [form, updateConfig, queryClient]);

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
      onSuccess: (data) => {
        queryClient.setQueryData(["config"], data);
        message.success("问财数据源配置已保存");
      },
      onError: (err: Error) => {
        message.error(`保存失败: ${err.message}`);
      },
    });
  }, [form, updateConfig, queryClient]);

  const handleSaveTwitter = useCallback(() => {
    const raw = form.twitter_feeds ?? [];
    const cleaned = raw
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    updateConfig.mutate(
      { twitter_feeds: cleaned },
      {
        onSuccess: (data) => {
          queryClient.setQueryData(["config"], data);
          queryClient.invalidateQueries({ queryKey: ["marketTwitterFeed"] });
          message.success("Twitter 账号配置已保存");
        },
        onError: (err: Error) => {
          message.error(`保存失败: ${err.message}`);
        },
      },
    );
  }, [form, updateConfig, queryClient]);

  const handleSaveDataSourceCookies = useCallback(() => {
    const patch: ConfigUpdate = {};
    if (form.eastmoney_cookie && !form.eastmoney_cookie.endsWith("***")) {
      patch.eastmoney_cookie = form.eastmoney_cookie;
    }
    if (form.baidu_cookie && !form.baidu_cookie.endsWith("***")) {
      patch.baidu_cookie = form.baidu_cookie;
    }
    if (Object.keys(patch).length === 0) {
      message.info("没有需要保存的变更");
      return;
    }
    updateConfig.mutate(patch, {
      onSuccess: (data) => {
        queryClient.setQueryData(["config"], data);
        message.success("数据源 Cookie 配置已保存");
      },
      onError: (err: Error) => {
        message.error(`保存失败: ${err.message}`);
      },
    });
  }, [form, updateConfig, queryClient]);

  if (isLoading) {
    return (
      <div
        style={{
          ...pageContainerStyle,
          color: c.textSecondary,
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
          color: c.up,
          textAlign: "center",
          paddingTop: 80,
        }}
      >
        配置加载失败，请确认后端服务已启动。
        <div style={{ marginTop: 12, color: c.textMuted, fontSize: 12 }}>
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
          大模型、飞书、Notion、问财等为<strong>每账号独立的私密配置</strong>，仅对当前登录用户生效；
          修改后即时生效无需重启。
          {user && (
            <span style={{ marginLeft: 8, color: c.textMuted }}>
              当前账号：<strong style={{ color: c.textSecondary }}>{user.username}</strong>
              {user.is_admin && <Tag color="gold" style={{ marginLeft: 6 }}>管理员</Tag>}
            </span>
          )}
        </p>
      </div>

      {/* 账号安全（所有登录用户） */}
      <ChangePasswordCard />

      {/* 邀请码管理（仅管理员） */}
      {isAdmin && <InviteManagerCard />}

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
        <Divider style={{ borderColor: c.border, margin: "16px 0" }} />
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
        <Divider style={{ borderColor: c.border, margin: "16px 0" }} />
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
        <Divider style={{ borderColor: c.border, margin: "16px 0" }} />
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
        <Divider style={{ borderColor: c.border, margin: "16px 0" }} />
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveIwencai}
          loading={updateConfig.isPending}
        >
          保存问财配置
        </Button>
      </Card>

      {/* Twitter 财经账号配置（全局，仅管理员可改） */}
      {isAdmin && (
      <Card
        title={
          <span>
            <SearchOutlined style={{ marginRight: 8 }} />
            Twitter 财经账号配置（全局）
          </span>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <Row gutter={[24, 16]}>
          <Col span={24}>
            <div style={fieldLabelStyle}>
              Twitter/X 财经账号列表（每行一个，不含 @）
            </div>
            <Input.TextArea
              rows={4}
              value={(form.twitter_feeds ?? []).join("\n")}
              onChange={(e) =>
                set({ twitter_feeds: e.target.value.split("\n") })
              }
              placeholder={"qinbafrank\n账号2\n账号3"}
            />
            <div style={{ marginTop: 4, fontSize: 12, color: c.textMuted }}>
              用于拉取 Twitter/X 上的财经推文和文章，每行填写一个账号名（不带 @）
            </div>
          </Col>
        </Row>
        <Divider style={{ borderColor: c.border, margin: "16px 0" }} />
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveTwitter}
          loading={updateConfig.isPending}
        >
          保存 Twitter 配置
        </Button>
      </Card>
      )}

      {/* 数据源 Cookie（全局，仅管理员可改） */}
      {isAdmin && (
      <Card
        title={
          <span>
            <SearchOutlined style={{ marginRight: 8 }} />
            数据源 Cookie 配置（全局）
          </span>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <Row gutter={[24, 16]}>
          <Col span={24}>
            <div style={fieldLabelStyle}>东方财富 Cookie</div>
            <Input.Password
              value={form.eastmoney_cookie || ""}
              onChange={(e) => set({ eastmoney_cookie: e.target.value })}
              placeholder="留空使用内置默认值"
            />
            <div style={{ marginTop: 4, fontSize: 12, color: c.textMuted }}>
              从浏览器 DevTools → Network → 请求头中复制 Cookie 值
            </div>
          </Col>
          <Col span={24}>
            <div style={fieldLabelStyle}>百度 Cookie</div>
            <Input.Password
              value={form.baidu_cookie || ""}
              onChange={(e) => set({ baidu_cookie: e.target.value })}
              placeholder="留空使用内置默认值"
            />
            <div style={{ marginTop: 4, fontSize: 12, color: c.textMuted }}>
              从浏览器 DevTools → Network → 请求头中复制 Cookie 值
            </div>
          </Col>
        </Row>
        <Divider style={{ borderColor: c.border, margin: "16px 0" }} />
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={handleSaveDataSourceCookies}
          loading={updateConfig.isPending}
        >
          保存数据源 Cookie
        </Button>
      </Card>
      )}

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
                  background: c.elevatedBg,
                  border: `1px solid ${c.border}`,
                  borderRadius: 8,
                  fontSize: 12,
                }}
              >
                <Text strong style={{ color: c.primary, fontSize: 13 }}>
                  {PROVIDER_OPTIONS.find((p) => p.value === name)?.label || name}
                </Text>
                <div style={{ marginTop: 6, color: c.textSecondary }}>
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
