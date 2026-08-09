import { Tag } from "antd";
import type { QuantFormValues, StrategyOption } from "./quantForm";

interface StrategyPresetPickerProps {
  value: QuantFormValues["strategyType"];
  options: StrategyOption[];
  onChange: (value: QuantFormValues["strategyType"]) => void;
}

export default function StrategyPresetPicker({ value, options, onChange }: StrategyPresetPickerProps) {
  return (
    <div className="quant-strategy-preset-grid" role="radiogroup" aria-label="预制策略">
      {options.map((option) => {
        const isSelected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            className={`quant-strategy-preset${isSelected ? " is-selected" : ""}`}
            onClick={() => onChange(option.value)}
          >
            <span className="quant-strategy-preset-heading">
              <strong>{option.label}</strong>
              {isSelected ? <span className="quant-strategy-selected">已选择</span> : null}
            </span>
            <span className="quant-strategy-description">{option.description}</span>
            <span className="quant-strategy-meta">
              <span>适用行情：{option.scenario}</span>
              <Tag color={option.riskColor}>风险：{option.risk}</Tag>
            </span>
            <span className="quant-strategy-parameters-summary">默认参数：{option.parameterSummary}</span>
          </button>
        );
      })}
    </div>
  );
}
