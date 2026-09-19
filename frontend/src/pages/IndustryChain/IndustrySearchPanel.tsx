import { SearchOutlined } from "@ant-design/icons";
import { Input, Tag } from "antd";
import type { IndustryChainResearchScope } from "../../types/stock";
import IndustryResearchScopeControls from "./IndustryResearchScopeControls";

const { Search } = Input;

export interface IndustryHotTopic {
  name: string;
  icon: string;
}

interface IndustrySearchPanelProps {
  value: string;
  activeName: string;
  hasDisplayedResult: boolean;
  disabled: boolean;
  loading: boolean;
  hotIndustries: IndustryHotTopic[];
  scope: IndustryChainResearchScope;
  onValueChange: (value: string) => void;
  onSearch: (value: string) => void;
  onScopeChange: (scope: IndustryChainResearchScope) => void;
}

export default function IndustrySearchPanel({
  value,
  activeName,
  hasDisplayedResult,
  disabled,
  loading,
  hotIndustries,
  scope,
  onValueChange,
  onSearch,
  onScopeChange,
}: IndustrySearchPanelProps) {
  return (
    <>
      <Search
        placeholder="输入产业链名称，如：锂电池、AI芯片、光伏..."
        enterButton={(
          <span>
            <SearchOutlined /> {hasDisplayedResult && value.trim() === activeName ? "重新分析" : "开始分析"}
          </span>
        )}
        size="large"
        loading={loading}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        onSearch={onSearch}
        disabled={disabled}
      />
      <div className="industry-search-panel__hot-topics">
        <span>🔥 热门赛道:</span>
        {hotIndustries.map((item) => (
          <Tag
            key={item.name}
            className="industry-search-panel__hot-topic"
            aria-disabled={disabled}
            onClick={() => {
              if (disabled) return;
              onValueChange(item.name);
              onSearch(item.name);
            }}
          >
            {item.icon} {item.name}
          </Tag>
        ))}
      </div>
      <IndustryResearchScopeControls
        value={scope}
        disabled={disabled}
        onChange={onScopeChange}
      />
    </>
  );
}
