import {
  DashboardOutlined,
  LineChartOutlined,
  QuestionCircleOutlined,
  RiseOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { Button, Input, Select, Tag } from "antd";
import { useMemo, useState, type ReactNode } from "react";
import { semanticTagStyle } from "../../styles/ui";
import type { QuantFormValues, StrategyOption } from "./quantForm";

const STRATEGY_ICONS: Record<string, ReactNode> = {
  "line-chart": <LineChartOutlined />,
  rise: <RiseOutlined />,
  dashboard: <DashboardOutlined />,
  swap: <SwapOutlined />,
};

interface StrategyPresetPickerProps {
  value: QuantFormValues["strategyType"];
  options: StrategyOption[];
  parameterValues?: Record<string, number | boolean | string>;
  onChange: (value: QuantFormValues["strategyType"]) => void;
}

export default function StrategyPresetPicker({ value, options, parameterValues, onChange }: StrategyPresetPickerProps) {
  const [isCatalogOpen, setIsCatalogOpen] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [riskLevel, setRiskLevel] = useState<string>();
  const [scenario, setScenario] = useState<string>();
  const scenarioOptions = useMemo(() => Array.from(new Set(options.map((option) => option.scenario)))
    .sort((left, right) => left.localeCompare(right, "zh-CN"))
    .map((item) => ({ value: item, label: item })), [options]);
  const filtered = useMemo(() => {
    const normalized = keyword.trim().toLowerCase();
    return options.filter((option) => {
      if (riskLevel && option.riskLevel !== riskLevel) return false;
      if (scenario && option.scenario !== scenario) return false;
      if (!normalized) return true;
      return [option.label, option.value, option.description, option.scenario]
        .some((text) => text.toLowerCase().includes(normalized));
    });
  }, [keyword, options, riskLevel, scenario]);
  const selected = options.find((option) => option.value === value);
  const actualParameterSummary = selected?.parameters.map((parameter) => (
    `${parameter.label} ${String(parameterValues?.[parameter.key]
      ?? selected.config.parameters?.[parameter.key]
      ?? parameter.default)}`
  )).join(" · ");
  const hasModifiedParameters = Boolean(selected?.parameters.some((parameter) => (
    (parameterValues?.[parameter.key] ?? selected.config.parameters?.[parameter.key] ?? parameter.default)
      !== (selected.config.parameters?.[parameter.key] ?? parameter.default)
  )));
  const catalogVisible = isCatalogOpen || !selected;
  const visibleOptions = selected && !filtered.some((option) => option.value === selected.value)
    ? [selected, ...filtered]
    : filtered;

  return (
    <div className="quant-strategy-picker">
      {selected ? (
        <div className="quant-selected-strategy">
          <span className="quant-strategy-icon" aria-hidden="true">
            {STRATEGY_ICONS[selected.icon] ?? <QuestionCircleOutlined />}
          </span>
          <span className="quant-selected-strategy-copy">
            <strong>当前策略：{selected.label}</strong>
            <span>{selected.scenario} · 风险{selected.risk}</span>
            <span>实际参数：{actualParameterSummary || "默认参数"}</span>
          </span>
          <span className="quant-selected-strategy-actions">
            {hasModifiedParameters ? <Tag style={semanticTagStyle("warning")}>已修改</Tag> : null}
            <Button size="small" onClick={() => setIsCatalogOpen((current) => !current)}>
              {isCatalogOpen ? "收起策略" : "更换策略"}
            </Button>
          </span>
        </div>
      ) : null}
      {catalogVisible ? <>
        <div className="quant-strategy-filters">
        <Input
          allowClear
          aria-label="搜索预制策略"
          placeholder="搜索策略名称或 key"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
        />
        <Select
          allowClear
          aria-label="策略风险"
          placeholder="风险等级"
          value={riskLevel}
          onChange={setRiskLevel}
          options={[
            { value: "low", label: "较低风险" },
            { value: "medium", label: "中等风险" },
            { value: "high", label: "较高风险" },
          ]}
        />
        <Select
          allowClear
          aria-label="适用行情"
          placeholder="适用行情"
          value={scenario}
          onChange={setScenario}
          options={scenarioOptions}
        />
        <span className="quant-strategy-filter-count">匹配 {filtered.length}/{options.length}</span>
        </div>
        <div className="quant-strategy-preset-grid" role="radiogroup" aria-label="预制策略">
        {visibleOptions.map((option) => {
          const isSelected = option.value === value;
          return (
            <button
              key={`${option.value}@${option.version}`}
              type="button"
              role="radio"
              aria-checked={isSelected}
              className={`quant-strategy-preset${isSelected ? " is-selected" : ""}`}
              onClick={() => {
                onChange(option.value);
                setIsCatalogOpen(false);
              }}
            >
              <span className="quant-strategy-preset-heading">
                <span className="quant-strategy-title">
                  <span className="quant-strategy-icon" aria-hidden="true">
                    {STRATEGY_ICONS[option.icon] ?? <QuestionCircleOutlined />}
                  </span>
                  <strong>{option.label}</strong>
                </span>
                {isSelected ? <span className="quant-strategy-selected">已选择</span> : null}
              </span>
              <span className="quant-strategy-description">{option.description}</span>
              <span className="quant-strategy-meta">
                <span>适用行情：{option.scenario}</span>
                <span>版本：{option.version}</span>
                <Tag style={semanticTagStyle(option.riskColor)}>风险：{option.risk}</Tag>
              </span>
              <span className="quant-strategy-parameters-summary">默认参数：{option.parameterSummary}</span>
            </button>
          );
        })}
        {visibleOptions.length === 0 ? <div className="quant-strategy-empty">没有匹配的预制策略</div> : null}
        </div>
      </> : null}
    </div>
  );
}
