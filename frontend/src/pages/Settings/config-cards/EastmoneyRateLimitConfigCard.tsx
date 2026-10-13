import { useMemo } from "react";
import { ThunderboltOutlined } from "@ant-design/icons";
import { Alert, Col, InputNumber, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";
import type { ConfigUpdate } from "../../../types/settings";

export const EASTMONEY_RATE_LIMIT_KEYS = [
  "eastmoney_min_interval_seconds",
  "eastmoney_datacenter_min_interval_seconds",
  "eastmoney_cooldown_seconds",
  "eastmoney_datacenter_cooldown_seconds",
  "eastmoney_jitter_min_seconds",
  "eastmoney_jitter_max_seconds",
  "eastmoney_transient_failure_threshold",
] as const satisfies readonly (keyof ConfigUpdate)[];

export type EastmoneyRateLimitKey = (typeof EASTMONEY_RATE_LIMIT_KEYS)[number];

type RateLimitKey = EastmoneyRateLimitKey;

interface NumberFieldSpec {
  key: RateLimitKey;
  label: string;
  hint: string;
  min: number;
  max: number;
  step: number;
  fallback: number;
}

const INTERVAL_FIELDS: NumberFieldSpec[] = [
  {
    key: "eastmoney_min_interval_seconds",
    label: "行情接口请求间隔（秒）",
    hint: "push2 / push2his 等行情接口两次请求之间的最小间隔。",
    min: 0,
    max: 60,
    step: 0.1,
    fallback: 1,
  },
  {
    key: "eastmoney_datacenter_min_interval_seconds",
    label: "数据中心请求间隔（秒）",
    hint: "龙虎榜、解禁等 datacenter 接口的最小请求间隔。",
    min: 0,
    max: 60,
    step: 0.1,
    fallback: 1,
  },
];

const COOLDOWN_FIELDS: NumberFieldSpec[] = [
  {
    key: "eastmoney_cooldown_seconds",
    label: "行情接口冷却时长（秒）",
    hint: "触发风控（HTTP 403/429）或连续失败后，暂停该主机请求的时长。",
    min: 0,
    max: 86400,
    step: 10,
    fallback: 120,
  },
  {
    key: "eastmoney_datacenter_cooldown_seconds",
    label: "数据中心冷却时长（秒）",
    hint: "数据中心接口的冷却时长，可比行情接口更短。",
    min: 0,
    max: 86400,
    step: 10,
    fallback: 10,
  },
];

const JITTER_MIN_KEY: RateLimitKey = "eastmoney_jitter_min_seconds";
const JITTER_MAX_KEY: RateLimitKey = "eastmoney_jitter_max_seconds";
const THRESHOLD_KEY: RateLimitKey = "eastmoney_transient_failure_threshold";

function renderField(
  field: NumberFieldSpec,
  form: ConfigUpdate,
  onChange: (patch: ConfigUpdate) => void,
  labelStyle: React.CSSProperties,
  colors: ReturnType<typeof useColors>,
) {
  const value = form[field.key] as number | undefined;
  return (
    <Col xs={24} md={12} key={field.key}>
      <div style={labelStyle}>{field.label}</div>
      <InputNumber
        aria-label={field.label}
        min={field.min}
        max={field.max}
        step={field.step}
        style={{ width: "100%" }}
        value={value ?? field.fallback}
        onChange={(next) => onChange({ [field.key]: (next ?? field.fallback) as number })}
      />
      <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
        {field.hint}
      </div>
    </Col>
  );
}

export default function EastmoneyRateLimitConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  stretch,
  isDirty,
  onReset,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  // 抖动上限必须不小于下限，否则 base.py 里的 max(jitter_min, jitter_max) 会静默改写配置
  const jitterWarning = useMemo(() => {
    const min = form[JITTER_MIN_KEY] as number | undefined;
    const max = form[JITTER_MAX_KEY] as number | undefined;
    if (min === undefined || max === undefined) return null;
    if (max < min) return `抖动上限（${max}）小于下限（${min}），实际会按下限执行`;
    return null;
  }, [form]);

  return (
    <SettingsCard
      title="东方财富限流与风控"
      icon={<ThunderboltOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存东财限流配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        title="调低限流会提高被风控封禁的概率"
        description="东方财富按访问频率做风控，间隔过小或冷却过短会触发 HTTP 403/429 并延长封禁。仅在确认触发风控时才建议调小。"
      />

      <div style={{ fontSize: "var(--c-font-sm)", fontWeight: 600, marginBottom: 8 }}>请求间隔</div>
      <Row gutter={[24, 16]}>
        {INTERVAL_FIELDS.map((field) => renderField(field, form, onChange, fieldLabelStyle, colors))}
      </Row>

      <div style={{ fontSize: "var(--c-font-sm)", fontWeight: 600, margin: "20px 0 8px" }}>风控冷却</div>
      <Row gutter={[24, 16]}>
        {COOLDOWN_FIELDS.map((field) => renderField(field, form, onChange, fieldLabelStyle, colors))}
      </Row>

      <div style={{ fontSize: "var(--c-font-sm)", fontWeight: 600, margin: "20px 0 8px" }}>抖动与失败阈值</div>
      <Row gutter={[24, 16]}>
        <Col xs={24} md={8}>
          <div style={fieldLabelStyle}>抖动下限（秒）</div>
          <InputNumber
            aria-label="抖动下限"
            min={0}
            max={60}
            step={0.1}
            style={{ width: "100%" }}
            value={(form[JITTER_MIN_KEY] as number | undefined) ?? 0.1}
            onChange={(next) => onChange({ [JITTER_MIN_KEY]: (next ?? 0.1) as number })}
          />
        </Col>
        <Col xs={24} md={8}>
          <div style={fieldLabelStyle}>抖动上限（秒）</div>
          <InputNumber
            aria-label="抖动上限"
            min={0}
            max={60}
            step={0.1}
            style={{ width: "100%" }}
            value={(form[JITTER_MAX_KEY] as number | undefined) ?? 0.5}
            onChange={(next) => onChange({ [JITTER_MAX_KEY]: (next ?? 0.5) as number })}
          />
        </Col>
        <Col xs={24} md={8}>
          <div style={fieldLabelStyle}>连续失败阈值</div>
          <InputNumber
            aria-label="连续失败阈值"
            min={1}
            max={100}
            step={1}
            style={{ width: "100%" }}
            value={(form[THRESHOLD_KEY] as number | undefined) ?? 3}
            onChange={(next) => onChange({ [THRESHOLD_KEY]: (next ?? 3) as number })}
          />
        </Col>
      </Row>
      <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: jitterWarning ? colors.warning : colors.textMuted }}>
        {jitterWarning ?? "抖动为每次请求追加的随机等待，避免固定节奏被识别；达到失败阈值即触发冷却。"}
      </div>
    </SettingsCard>
  );
}

