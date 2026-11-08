import {
  ApiOutlined,
  CloudDownloadOutlined,
  RobotOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import {
  Alert,
  AutoComplete,
  Button,
  Col,
  Collapse,
  Input,
  InputNumber,
  Row,
  Select,
  Slider,
  Switch,
  Tag,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { useStyles } from "../../../styles/ui";
import "../styles/llm-config.css";
import { useFetchLlmModels } from "../../../api/queryHooks/settings";
import type { LlmApiMode, ProviderDefault } from "../../../types/settings";
import { PROVIDER_MODEL_PAIRS, PROVIDER_RECOMMENDED_SUB_MODELS } from "../llmModelPairs";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

const API_MODE_OPTIONS: Array<{ value: LlmApiMode; label: string }> = [
  { value: "auto", label: "自动（跟随 Provider）" },
  { value: "openai", label: "OpenAI Compatible" },
  { value: "litellm", label: "LiteLLM" },
];

// 键必须与后端 provider_catalog 的 provider 名称一致，否则推荐列表不显示。
const PROVIDER_RECOMMENDED_MODELS: Record<string, string[]> = {
  deepseek: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4.1", "deepseek-reasoner", "deepseek-chat"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-5-mini", "o3-mini"],
  claude: ["anthropic/claude-sonnet-4-6", "anthropic/claude-haiku-4-5"],
  gemini: ["gemini/gemini-2.5-flash", "gemini/gemini-2.5-pro"],
  qwen: ["qwen-plus", "qwen-max", "qwen-turbo", "qwen3-max"],
  siliconflow: ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-72B-Instruct"],
  ollama: ["qwen3:8b", "deepseek-r1:8b", "qwen2.5:7b", "llama3.1:8b"],
  zhipu: ["GLM-4.7-Flash", "glm-4-plus", "glm-4-air"],
  moonshot: ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
  openrouter: ["openai/gpt-4o-mini", "anthropic/claude-sonnet-4-6", "google/gemini-2.5-flash"],
  azure: ["azure/YOUR_DEPLOYMENT"],
  custom: [],
};

/** extra_body 以 JSON 文本编辑：非法 JSON 不写回表单，避免把坏值提交到后端。 */
function formatExtraBody(value: Record<string, unknown> | undefined): string {
  return JSON.stringify(value ?? {}, null, 2);
}

interface LlmConfigCardProps extends ConfigCardProps {
  onProviderChange: (provider: string) => void;
  providerDefaults: Record<string, ProviderDefault>;
  /** 仍沿用管理员（全局）配置的字段名，由 `GET /api/config` 的 inherited_keys 提供 */
  inheritedKeys?: string[];
  /** 当前用户是否管理员（管理员本身就是全局配置来源，不显示"改用管理员配置"） */
  isAdmin?: boolean;
  /** 一键清空个人 LLM 覆盖，改为沿用管理员配置（保存动作由上层携带显式补丁完成） */
  onUseAdminConfig?: () => void;
}

export default function LlmConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  onProviderChange,
  providerDefaults,
  inheritedKeys = [],
  isAdmin = false,
  onUseAdminConfig,
  isDirty,
  onReset,
}: LlmConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const inheritsEndpoint = ["llm_provider", "llm_base_url"].every((key) =>
    inheritedKeys.includes(key),
  );
  const inheritsKey = inheritedKeys.includes("llm_api_key");
  // 端点与 Key 必须成对设置：URL 和 Key 都在继承时，即为沿用管理员配置
  const usesAdminLlm = inheritsEndpoint && inheritsKey;
  const sourceLabel = isAdmin
    ? "全局配置"
    : usesAdminLlm
      ? "沿用管理员配置"
      : "个人端点";
  const sourceHint = isAdmin
    ? "这里的改动会同步为全局配置，供后台任务与未单独配置的用户使用。"
    : usesAdminLlm
      ? "留空即沿用管理员端点与 Key（可单独修改模型和温度）；若自定义需同时设置 Base URL 与 API Key。"
      : "自定义端点模式（Base URL 与 API Key 必须成对配置）。点击「改用管理员配置」可随时恢复。";
  const selectedDefaults = form.llm_provider ? providerDefaults[form.llm_provider] : undefined;
  const [fetchedModels, setFetchedModels] = useState<string[] | null>(null);
  const serializedExtraBody = formatExtraBody(form.llm_extra_body);
  const [extraBodyText, setExtraBodyText] = useState(serializedExtraBody);
  const [extraBodyError, setExtraBodyError] = useState<string | null>(null);

  // 仅当生效值真的变化（保存/撤销）时回填文本，避免打断正在输入的内容。
  useEffect(() => {
    setExtraBodyText((current) => {
      try {
        if (JSON.stringify(JSON.parse(current)) === JSON.stringify(JSON.parse(serializedExtraBody))) {
          return current;
        }
      } catch {
        // 当前文本非法：交给用户继续编辑，不回填覆盖。
      }
      return serializedExtraBody;
    });
  }, [serializedExtraBody]);

  const handleExtraBodyChange = (text: string) => {
    setExtraBodyText(text);
    if (!text.trim()) {
      setExtraBodyError(null);
      onChange({ llm_extra_body: {} });
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch (error) {
      setExtraBodyError(`JSON 解析失败：${(error as Error).message}`);
      return;
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      setExtraBodyError("extra_body 必须是 JSON 对象");
      return;
    }
    setExtraBodyError(null);
    onChange({ llm_extra_body: parsed as Record<string, unknown> });
  };
  const fetchModelsMutation = useFetchLlmModels();
  const recommendedModels: string[] = PROVIDER_RECOMMENDED_MODELS[form.llm_provider ?? ""] ?? [];

  const handleFetchModels = () => {
    fetchModelsMutation.mutate(
      {
        base_url: form.llm_base_url || "",
        api_key: form.llm_api_key || "",
        api_mode: form.llm_api_mode || "",
        api_version: form.llm_api_version || "",
      },
      {
        onSuccess: (data) => {
          setFetchedModels(data.models);
          message.success(`已获取 ${data.models.length} 个模型`);
        },
        onError: (error: Error) => message.error(`获取模型列表失败：${error.message}`),
      },
    );
  };

  const providerOptions = Object.entries(providerDefaults).map(([value, defaults]) => ({
    value,
    label: defaults.label || value,
  }));

  return (
    <SettingsCard
      title="大模型配置"
      icon={<RobotOutlined className="llm-config-icon--mr-8" />}
      saveLabel="保存大模型配置"
      onSave={onSave}
      isSaving={isSaving}
      isDirty={isDirty}
      onReset={onReset}
    >
      <div
        className={`llm-config-banner ${
          isAdmin
            ? "is-admin"
            : usesAdminLlm
              ? "is-admin-llm"
              : inheritsEndpoint
                ? "is-inherits-endpoint"
                : "is-custom"
        }`}
      >
        <div className="llm-config-banner__left">
          <Tag color={isAdmin ? "purple" : usesAdminLlm ? "blue" : "gold"} className="llm-config-banner__tag">
            {sourceLabel}
          </Tag>
          <span className="u-text-secondary">{sourceHint}</span>
        </div>
        {!isAdmin && !usesAdminLlm && onUseAdminConfig && (
          <Button
            size="small"
            onClick={onUseAdminConfig}
            className="llm-config-banner__btn"
          >
            改用管理员配置
          </Button>
        )}
      </div>
      <Row gutter={[24, 16]}>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Provider</div>
          <Select
            value={form.llm_provider}
            onChange={onProviderChange}
            options={providerOptions}
            className="u-w-full"
          />
          {selectedDefaults?.description && (
            <div className="u-field-hint">
              {selectedDefaults.description}
            </div>
          )}
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>
            API Key{selectedDefaults && !selectedDefaults.api_key_required ? "（可选）" : ""}
          </div>
          <Input.Password
            value={form.llm_api_key || ""}
            onChange={(event) => onChange({ llm_api_key: event.target.value })}
            placeholder={
              selectedDefaults?.api_key_required === false
                ? "本地服务可留空"
                : inheritsEndpoint
                  ? "留空即使用管理员配置的 Key；若自定义需在下方同时填写 Base URL"
                  : "请输入该端点对应的 API Key"
            }
          />
          <div className="u-field-hint">
            {selectedDefaults?.api_key_required === false
              ? "本地服务无需 Key，可直接留空。"
              : inheritsEndpoint
                ? "沿用管理员 Key（可单独修改模型/温度）；若需自定义端点，请在下方同时设置 Base URL 与 API Key。"
                : "自定义端点模式：需同时配置 Base URL 与有效的 API Key。"}
          </div>
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Model</div>
          <div className="llm-config-model-row">
            <AutoComplete
              className="llm-config-model-input"
              value={form.llm_model || ""}
              onChange={(value) => onChange({ llm_model: value })}
              options={(fetchedModels ?? recommendedModels).map((m) => ({ value: m }))}
              filterOption={(input, option) =>
                String(option?.value ?? "").toLowerCase().includes(input.toLowerCase())
              }
              placeholder={selectedDefaults?.model || "输入或从列表选择"}
            />
            <Button
              icon={<CloudDownloadOutlined />}
              onClick={handleFetchModels}
              loading={fetchModelsMutation.isPending}
              title="按 Base URL 与 API Key 拉取可用模型列表"
            >
              获取模型
            </Button>
          </div>
          {form.llm_provider && PROVIDER_MODEL_PAIRS[form.llm_provider] ? (
            <div className="llm-config-presets-row">
              <span className="llm-config-presets-label">推荐搭配:</span>
              <Tag
                color="blue"
                className="llm-config-preset-tag"
                onClick={() => {
                  const pair = PROVIDER_MODEL_PAIRS[form.llm_provider!];
                  onChange({ llm_model: pair.main, llm_sub_model: pair.sub });
                  message.success(`已套用推荐搭配：主模型 ${pair.main} + 子模型 ${pair.sub}`);
                }}
                title="一键套用该服务商推荐的主模型与轻量子模型搭配"
              >
                ⚡ 主 {PROVIDER_MODEL_PAIRS[form.llm_provider].main} + 子 {PROVIDER_MODEL_PAIRS[form.llm_provider].sub}（一键套用）
              </Tag>
            </div>
          ) : null}
          {form.llm_provider && PROVIDER_RECOMMENDED_MODELS[form.llm_provider] ? (
            <div className="llm-config-presets-row">
              <span className="llm-config-presets-label">常用模型:</span>
              {PROVIDER_RECOMMENDED_MODELS[form.llm_provider].map((m) => (
                <Tag
                  key={m}
                  className={`llm-config-preset-tag ${form.llm_model === m ? "is-active" : ""}`}
                  onClick={() => onChange({ llm_model: m })}
                >
                  {m}
                </Tag>
              ))}
            </div>
          ) : null}
          {fetchedModels && fetchedModels.length > 0 ? (
            <div className="llm-config-presets-row">
              <span className="llm-config-presets-label">在线模型:</span>
              <Tag color="blue" className="llm-config-preset-tag">
                已获取 {fetchedModels.length} 个
              </Tag>
            </div>
          ) : null}
        </Col>
        <Col span={24} sm={12}>
          <div className="u-field-label--row">
            <span>Temperature: {form.llm_temperature ?? 0.1}</span>
            <span className="llm-config-presets-label">
              {(form.llm_temperature ?? 0.1) <= 0.2 ? "严谨精确" : (form.llm_temperature ?? 0.1) <= 0.5 ? "均衡通用" : "丰富发散"}
            </span>
          </div>
          <Row gutter={12} align="middle">
            <Col flex="auto">
              <Slider
                min={0}
                max={1}
                step={0.05}
                value={form.llm_temperature ?? 0.1}
                onChange={(value) => onChange({ llm_temperature: value })}
              />
            </Col>
            <Col flex="68px">
              <InputNumber
                min={0}
                max={1}
                step={0.05}
                value={form.llm_temperature ?? 0.1}
                onChange={(value) => onChange({ llm_temperature: value ?? 0.1 })}
                className="u-w-full"
                size="small"
              />
            </Col>
          </Row>
          <div className="llm-config-presets-row">
            {[
              { label: "严谨 0.0", value: 0.0 },
              { label: "推荐 0.1", value: 0.1 },
              { label: "平衡 0.3", value: 0.3 },
              { label: "发散 0.7", value: 0.7 },
            ].map((preset) => (
              <Tag
                key={preset.value}
                className={`llm-config-preset-tag ${(form.llm_temperature ?? 0.1) === preset.value ? "is-active" : ""}`}
                onClick={() => onChange({ llm_temperature: preset.value })}
              >
                {preset.label}
              </Tag>
            ))}
          </div>
        </Col>
        <Col span={24}>
          <Collapse
            size="small"
            defaultActiveKey={inheritsEndpoint ? [] : ["endpoint"]}
            items={[
              {
                key: "endpoint",
                label: (
                  <span>
                    <ApiOutlined className="llm-config-icon--mr-6" />
                    端点与模型（Base URL / API 模式 / 子模型 / 上下文长度）
                    <span className="llm-config-subtext--ml-8 llm-config-presets-label">
                      留空即沿用管理员配置
                    </span>
                  </span>
                ),
                children: (
                  <Row gutter={[24, 16]}>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Base URL</div>
          <Input
            value={form.llm_base_url || ""}
            onChange={(event) => onChange({ llm_base_url: event.target.value })}
            placeholder={selectedDefaults?.base_url || "https://api.openai.com/v1"}
          />
          {selectedDefaults?.base_url ? (
            <div className="llm-config-presets-row">
              <span className="llm-config-presets-label">预设地址:</span>
              <Tag
                className={`llm-config-preset-tag ${form.llm_base_url === selectedDefaults.base_url ? "is-active" : ""}`}
                onClick={() => onChange({ llm_base_url: selectedDefaults.base_url })}
                title="点击填充官方默认 Base URL"
              >
                {selectedDefaults.base_url}
              </Tag>
            </div>
          ) : null}
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API 模式</div>
          <Select<LlmApiMode>
            value={form.llm_api_mode || "auto"}
            onChange={(value) => onChange({ llm_api_mode: value })}
            options={API_MODE_OPTIONS}
            className="u-w-full"
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
        <Col span={24}>
          <div className="u-field-label--row">
            <span>子模型（简单任务，可选）</span>
            {form.llm_sub_model && (
              <Button
                type="link"
                size="small"
                className="llm-config-inline-link"
                onClick={() => onChange({ llm_sub_model: "" })}
              >
                清空（跟随主模型）
              </Button>
            )}
          </div>
          <AutoComplete
            aria-label="子模型"
            className="u-w-full"
            value={form.llm_sub_model || ""}
            onChange={(value) => onChange({ llm_sub_model: value })}
            options={(fetchedModels ?? recommendedModels).map((m) => ({ value: m }))}
            filterOption={(input, option) =>
              String(option?.value ?? "").toLowerCase().includes(input.toLowerCase())
            }
            placeholder="留空则复用主模型"
            allowClear
          />
          {form.llm_provider && PROVIDER_RECOMMENDED_SUB_MODELS[form.llm_provider]?.length ? (
            <div className="llm-config-presets-row">
              <span className="llm-config-presets-label">
                常用子模型:
              </span>
              {PROVIDER_RECOMMENDED_SUB_MODELS[form.llm_provider].map((m) => (
                <Tag
                  key={m}
                  className={`llm-config-preset-tag ${form.llm_sub_model === m ? "is-active" : ""}`}
                  onClick={() => onChange({ llm_sub_model: m })}
                >
                  {m}
                </Tag>
              ))}
            </div>
          ) : null}
          {fetchedModels && fetchedModels.length > 0 && form.llm_sub_model && !fetchedModels.includes(form.llm_sub_model) ? (
            <Alert
              type="warning"
              showIcon
              className="llm-config-submodel-alert"
              title={
                <div className="llm-config-submodel-alert__content">
                  <span>
                    当前子模型 <code>{form.llm_sub_model}</code> 不在已获取的服务端模型列表中，简单任务可能因找不到模型而失败。
                  </span>
                  <Button size="small" onClick={() => onChange({ llm_sub_model: "" })}>
                    改为跟随主模型
                  </Button>
                </div>
              }
            />
          ) : null}
          <div className="u-field-hint">
            高频简单任务（如资讯逐条解读）改用更轻量的子模型，可显著降低超时概率；与主模型共用 Provider / Base URL / API Key。留空则直接复用主模型。
          </div>
        </Col>
        <Col span={24}>
          <div className="u-field-label--row">
            <span>降级备用模型（429/限流/超额兜底，可选）</span>
            {form.llm_fallback_model && (
              <Button
                type="link"
                size="small"
                className="llm-config-inline-link"
                onClick={() => onChange({ llm_fallback_model: "" })}
              >
                清空（不降级）
              </Button>
            )}
          </div>
          <AutoComplete
            aria-label="降级备用模型"
            className="u-w-full"
            value={form.llm_fallback_model || ""}
            onChange={(value) => onChange({ llm_fallback_model: value })}
            options={(fetchedModels ?? recommendedModels).map((m) => ({ value: m }))}
            filterOption={(input, option) =>
              String(option?.value ?? "").toLowerCase().includes(input.toLowerCase())
            }
            placeholder="主模型 429 quota exceeded 或不可用时自动切换的备用模型；留空则不降级"
            allowClear
          />
          <div className="u-field-hint">
            当主模型发生 429 额度超限（Quota Exceeded）、限流或多次重试仍不可用时，系统自动无缝切换到此模型继续执行，避免对话或分析失败中断。与主模型共用 Provider / Base URL / API Key。
          </div>
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>子模型启用任务（可选）</div>
          <Input
            aria-label="子模型任务清单"
            value={form.llm_simple_tasks || ""}
            onChange={(event) => onChange({ llm_simple_tasks: event.target.value })}
            placeholder="留空=全部"
          />
          <div className="u-field-hint">
            可选：chat_routing（对话意图分类）、macro_item（宏观逐条解读）、news_analysis（资讯归类）、twitter_analysis（推文分析）；逗号分隔。
          </div>
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>模型上下文长度（tokens）</div>
          <InputNumber
            min={0}
            max={2_000_000}
            step={1000}
            value={form.llm_context_length_tokens ?? 0}
            onChange={(value) => onChange({ llm_context_length_tokens: value ?? 0 })}
            className="u-w-full"
            placeholder="0 = 未设置"
          />
        </Col>
        <Col span={24}>
          <div className="llm-config-subtext-block">
            填写模型实际上下文窗口（如 32768 / 131072）。设置后对话历史会按该窗口自动裁剪，避免“超出模型上下文长度”报错；0 表示未设置，沿用默认历史上限。
          </div>
        </Col>
                  </Row>
                ),
              },
            ]}
          />
        </Col>
        <Col span={24}>
          <Collapse
            size="small"
            items={[
              {
                key: "advanced",
                label: (
                  <span>
                    <SettingOutlined className="llm-config-icon--mr-6" />
                    高级：超时 / 重试 / 输出预算 / 兼容字段
                    <span className="llm-config-subtext--ml-8 llm-config-presets-label">
                      留空或默认值即可，仅排障时调整
                    </span>
                  </span>
                ),
                children: (
                  <Row gutter={[24, 16]}>
                    <Col span={24} sm={12}>
                      <div style={fieldLabelStyle}>单次请求超时（秒）</div>
                      <InputNumber
                        aria-label="单次请求超时"
                        min={1}
                        max={3600}
                        value={form.llm_timeout_seconds ?? undefined}
                        onChange={(value) => onChange({ llm_timeout_seconds: value ?? undefined })}
                        className="u-w-full"
                      />
                    </Col>
                    <Col span={24} sm={12}>
                      <div style={fieldLabelStyle}>失败重试次数（含首次，1–3）</div>
                      <InputNumber
                        aria-label="失败重试次数"
                        min={1}
                        max={3}
                        value={form.llm_max_attempts ?? undefined}
                        onChange={(value) => onChange({ llm_max_attempts: value ?? undefined })}
                        className="u-w-full"
                      />
                    </Col>
                    <Col span={24} sm={12}>
                      <div style={fieldLabelStyle}>单次生成总时限（秒）</div>
                      <InputNumber
                        aria-label="单次生成总时限"
                        min={1}
                        step={60}
                        value={form.llm_generation_timeout_seconds ?? undefined}
                        onChange={(value) => onChange({ llm_generation_timeout_seconds: value ?? undefined })}
                        className="u-w-full"
                      />
                    </Col>
                    <Col span={24} sm={12}>
                      <div style={fieldLabelStyle}>普通生成输出预算（tokens）</div>
                      <InputNumber
                        aria-label="普通生成输出预算"
                        min={1}
                        step={512}
                        value={form.llm_generation_max_completion_tokens ?? undefined}
                        onChange={(value) => onChange({ llm_generation_max_completion_tokens: value ?? undefined })}
                        className="u-w-full"
                      />
                    </Col>
                    <Col span={24} sm={12}>
                      <div style={fieldLabelStyle}>模型输出上限（可选硬覆盖）</div>
                      <InputNumber
                        aria-label="模型输出上限"
                        min={1}
                        step={512}
                        value={form.llm_model_max_completion_tokens ?? undefined}
                        onChange={(value) => onChange({ llm_model_max_completion_tokens: value ?? null })}
                        className="u-w-full"
                        placeholder="未设置"
                      />
                    </Col>
                    <Col span={24} sm={12}>
                      <div style={fieldLabelStyle}>JSON 对象模式</div>
                      <Switch
                        aria-label="JSON 对象模式"
                        checked={form.llm_json_mode_enabled ?? true}
                        onChange={(checked) => onChange({ llm_json_mode_enabled: checked })}
                      />
                      <span className="llm-config-subtext--ml-8 llm-config-presets-label">
                        网关不支持 response_format 时关闭
                      </span>
                    </Col>
                    <Col span={24} sm={12}>
                      <div style={fieldLabelStyle}>流式用量统计</div>
                      <Switch
                        aria-label="流式用量统计"
                        checked={form.llm_stream_include_usage ?? true}
                        onChange={(checked) => onChange({ llm_stream_include_usage: checked })}
                      />
                      <span className="llm-config-subtext--ml-8 llm-config-presets-label">
                        stream_options 被网关拒绝时关闭
                      </span>
                    </Col>
                    <Col span={24}>
                      <div style={fieldLabelStyle}>厂商私有请求字段 extra_body（JSON 对象）</div>
                      <Input.TextArea
                        aria-label="extra_body"
                        value={extraBodyText}
                        onChange={(event) => handleExtraBodyChange(event.target.value)}
                        rows={4}
                        status={extraBodyError ? "error" : undefined}
                        spellCheck={false}
                        placeholder={'例：{"chat_template_kwargs": {"enable_thinking": true}}'}
                      />
                      <div className={`u-field-hint ${extraBodyError ? "llm-config-error-text" : ""}`}>
                        {extraBodyError
                          ? extraBodyError
                          : "用于打开 Qwen enable_thinking、GLM thinking 等兼容网关私有开关；model/messages/预算/协议参数不允许在此覆盖。"}
                      </div>
                      <div className="u-field-hint">
                        网关能力覆盖（Azure 部署名、自定义中转端点）属部署级配置，见 .env.example 的 LLM_COMPATIBILITY_OVERRIDES。
                      </div>
                    </Col>
                  </Row>
                ),
              },
            ]}
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}
