import { DeleteOutlined, HistoryOutlined, ReloadOutlined, SaveOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Col, Form, Input, InputNumber, Popconfirm, Row, Select, Switch, Tag, Tooltip, Typography } from "antd";
import { useState } from "react";
import {
  stockCodesValidationError,
  strategyConstraintDependencies,
  strategyConstraintValidationError,
  type QuantFormValues,
  type StrategyOption,
} from "./quantForm";
import StrategyPresetPicker from "./StrategyPresetPicker";

const { Text } = Typography;

interface SavedStrategyToolbarProps {
  selectedId?: number;
  options: Array<{ value: number; label: string }>;
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  onSelect: (strategyId?: number) => void;
  onSave: () => void;
  onDelete: () => void;
  onReset: () => void;
}

export function SavedStrategyToolbar({
  selectedId,
  options,
  isLoading,
  isSaving,
  isDeleting,
  onSelect,
  onSave,
  onDelete,
  onReset,
}: SavedStrategyToolbarProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const selectedName = options.find((option) => option.value === selectedId)?.label;
  return (
    <div className="quant-saved-manager">
      <Button
        type="text"
        icon={<SettingOutlined />}
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((current) => !current)}
      >
        策略配置管理{selectedName ? ` · ${selectedName}` : ""}
      </Button>
      {isExpanded ? <div className="quant-saved-toolbar">
      <div className="quant-saved-toolbar-heading">
        <HistoryOutlined />
        <span><strong>策略模板</strong><small>加载或保存常用参数组合</small></span>
      </div>
      <div className="quant-saved-toolbar-controls">
        <Select
          aria-label="已保存策略"
          value={selectedId}
          placeholder="加载已保存策略"
          allowClear
          loading={isLoading}
          options={options}
          onChange={(value) => onSelect(value ?? undefined)}
          className="quant-saved-select"
        />
        <div className="quant-saved-actions">
          <Button icon={<ReloadOutlined />} aria-label="恢复默认参数" onClick={onReset}>恢复默认</Button>
          <Button icon={<SaveOutlined />} loading={isSaving} onClick={onSave}>保存策略</Button>
          <Popconfirm
            title={`删除已保存策略“${selectedName ?? ""}”？`}
            description="删除后无法恢复"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            disabled={selectedId == null}
            onConfirm={onDelete}
          >
            <Button icon={<DeleteOutlined />} aria-label="删除已保存策略" danger disabled={selectedId == null} loading={isDeleting}>
              删除
            </Button>
          </Popconfirm>
        </div>
      </div>
      </div> : null}
    </div>
  );
}

export function FormSectionHeader({ title, description }: { title: string; description: string }) {
  const step = title.split(".", 1)[0].padStart(2, "0");
  return (
    <div className="quant-form-section-header">
      <span className="quant-form-step" aria-hidden="true">{step}</span>
      <span className="quant-form-section-copy">
        <Text strong>{title}</Text>
        <Text type="secondary">{description}</Text>
      </span>
    </div>
  );
}

const QUICK_STOCK_PRESETS = [
  { label: "贵州茅台", code: "600519" },
  { label: "宁德时代", code: "300750" },
  { label: "招商银行", code: "600036" },
  { label: "中国平安", code: "601318" },
  { label: "中芯国际", code: "688981" },
  { label: "长江电力", code: "600900" },
];

const THEMATIC_UNIVERSE_PRESETS = [
  {
    name: "沪深300白马",
    desc: "贵州茅台 / 宁德时代 / 中国平安 / 招商银行 / 比亚迪 / 长江电力 / 美的集团 / 紫金矿业",
    codes: "600519, 300750, 601318, 600036, 002594, 600900, 000333, 601899",
    color: "blue",
  },
  {
    name: "AI算力科技",
    desc: "中际旭创 / 新易盛 / 工业富联 / 澜起科技 / 中微公司 / 寒武纪",
    codes: "300308, 300502, 601138, 688008, 688012, 688256",
    color: "purple",
  },
  {
    name: "红利低波高股息",
    desc: "中国神华 / 陕西煤业 / 中国移动 / 工商银行 / 大秦铁路 / 中国石化",
    codes: "601088, 601225, 600941, 601398, 601006, 600028",
    color: "gold",
  },
  {
    name: "高端制造出海",
    desc: "比亚迪 / 汇川技术 / 阳光电源 / 三一重工 / 福耀玻璃",
    codes: "002594, 300124, 300274, 600031, 600660",
    color: "cyan",
  },
  {
    name: "医药医疗创新",
    desc: "恒瑞医药 / 药明康德 / 百济神州 / 迈瑞医疗 / 片仔癀",
    codes: "600276, 603259, 688235, 300760, 600436",
    color: "green",
  },
];

export function UniverseFields({ source }: { source: QuantFormValues["source"] }) {
  const form = Form.useFormInstance<QuantFormValues>();

  const handleQuickCode = (code: string) => {
    const current = (form.getFieldValue("codes") || "").trim();
    if (!current) {
      form.setFieldValue("codes", code);
      return;
    }
    const list = current.split(/[,\s，]+/).map((s: string) => s.trim()).filter(Boolean);
    if (!list.includes(code) && list.length < 30) {
      form.setFieldValue("codes", `${current}, ${code}`);
    }
  };

  const handleThematicPreset = (codes: string) => {
    form.setFieldsValue({
      source: "custom",
      codes,
    });
  };

  return (
    <section className="quant-form-section" aria-labelledby="quant-universe-title">
      <div id="quant-universe-title">
        <FormSectionHeader title="1. 回测范围" description="命名任务并确定参与回测的股票池" />
      </div>
      <Row gutter={[14, 0]} align="top">
        <Col xs={24} md={7}>
          <Form.Item name="name" label="回测名称" rules={[{ required: true, whitespace: true, message: "请输入回测名称" }]}>
            <Input maxLength={80} placeholder="例如：消费龙头双均线" />
          </Form.Item>
        </Col>
        <Col xs={24} sm={8} md={5}>
          <Form.Item name="source" label="股票池">
            <Select options={[
              { value: "custom", label: "自定义股票" },
              { value: "portfolio", label: "当前持仓" },
            ]} />
          </Form.Item>
        </Col>
        <Col xs={24} sm={16} md={12}>
          <Form.Item
            name="codes"
            label="股票代码"
            rules={[{
              validator: async (_, value?: string) => {
                const error = stockCodesValidationError(source, value);
                if (error) throw new Error(error);
              },
            }]}
            extra={source === "portfolio" ? "运行时读取当前持仓股票，最多 10 只" : "支持空格或逗号分隔，最多 30 只"}
          >
            <Input disabled={source === "portfolio"} placeholder="600519, 000001" />
          </Form.Item>
          {source === "custom" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "-12px", marginBottom: "12px" }}>
              <div className="quant-quick-stocks" style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>精选主题池:</span>
                {THEMATIC_UNIVERSE_PRESETS.map((preset) => (
                  <Tooltip key={preset.name} title={preset.desc}>
                    <Tag
                      color={preset.color}
                      style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0 }}
                      onClick={() => handleThematicPreset(preset.codes)}
                    >
                      {preset.name}
                    </Tag>
                  </Tooltip>
                ))}
              </div>
              <div className="quant-quick-stocks" style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>快捷加单股:</span>
                {QUICK_STOCK_PRESETS.map((preset) => (
                  <Tag
                    key={preset.code}
                    style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0 }}
                    onClick={() => handleQuickCode(preset.code)}
                  >
                    {preset.label}
                  </Tag>
                ))}
                <Tag
                  style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0, opacity: 0.7 }}
                  onClick={() => form.setFieldValue("codes", "")}
                >
                  清空
                </Tag>
              </div>
            </div>
          ) : null}
        </Col>
      </Row>
    </section>
  );
}

export function StrategyFields({
  strategyType,
  strategyOptions,
  parameterValues,
  onStrategyChange,
}: {
  strategyType: QuantFormValues["strategyType"];
  strategyOptions: StrategyOption[];
  parameterValues: QuantFormValues["strategyParameters"];
  onStrategyChange: (strategyType: QuantFormValues["strategyType"]) => void;
}) {
  const form = Form.useFormInstance<QuantFormValues>();
  const selectedStrategy = strategyOptions.find((option) => option.value === strategyType);
  return (
    <section className="quant-form-section" aria-labelledby="quant-strategy-title">
      <div id="quant-strategy-title">
        <FormSectionHeader title="2. 策略参数" description="选择交易逻辑并调整该策略的核心周期" />
      </div>
      <Form.Item name="strategyType" hidden>
        <Input />
      </Form.Item>
      <Form.Item name="strategyVersion" hidden>
        <Input />
      </Form.Item>
      <StrategyPresetPicker
        value={strategyType}
        options={strategyOptions}
        parameterValues={parameterValues}
        onChange={onStrategyChange}
      />
      <Row gutter={[14, 0]} align="bottom">
        {selectedStrategy?.parameters.map((parameter) => (
          <Col xs={12} sm={8} md={6} key={parameter.key}>
            <Form.Item
              name={["strategyParameters", parameter.key]}
              label={parameter.label}
              extra={parameter.description || undefined}
              valuePropName={parameter.type === "boolean" ? "checked" : "value"}
              dependencies={strategyConstraintDependencies(parameter.key, selectedStrategy.constraints)}
              rules={[
                { required: true, message: `请输入${parameter.label}` },
                {
                  validator: async () => {
                    const error = strategyConstraintValidationError(
                      parameter.key,
                      selectedStrategy.constraints,
                      form.getFieldValue("strategyParameters") ?? {},
                    );
                    if (error) throw new Error(error);
                  },
                },
              ]}
            >
              {parameter.choices?.length ? (
                <Select options={parameter.choices.map((value) => ({ value, label: String(value) }))} />
              ) : parameter.type === "boolean" ? (
                <Switch />
              ) : parameter.type === "integer" || parameter.type === "number" ? (
                <InputNumber
                  min={parameter.minimum ?? undefined}
                  max={parameter.maximum ?? undefined}
                  step={parameter.step ?? (parameter.type === "integer" ? 1 : undefined)}
                  precision={parameter.type === "integer" ? 0 : undefined}
                  style={{ width: "100%" }}
                />
              ) : (
                <Input maxLength={120} />
              )}
            </Form.Item>
          </Col>
        ))}
      </Row>
    </section>
  );
}
