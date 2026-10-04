import { useCallback, useMemo } from "react";
import { AutoComplete, Input, Tag } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import QueryErrorState from "../../components/QueryErrorState";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import { useColors } from "../../styles/ui";
import { buildStockProfileUrl } from "../../utils/stockLinks";

interface SearchBarProps {
  buildTarget?: (code: string) => string;
  ariaLabel?: string;
}

const buildDefaultTarget = buildStockProfileUrl;

export default function SearchBar({
  buildTarget = buildDefaultTarget,
  ariaLabel = "搜索股票",
}: SearchBarProps) {
  const {
    inputValue,
    normalizedInput,
    currentResults,
    isPending,
    isError,
    error,
    retry,
    setInputValue,
    clear,
    resolveCode,
  } = useStockSearchController();
  const navigate = useNavigate();
  const c = useColors();

  const options = useMemo(() => currentResults.map((item) => {
    const isHk = item.market === "hk" || /^\d{5}$/.test(item.code);
    return {
      value: item.code,
      label: (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            {isHk && (
              <Tag color="blue" style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                港股
              </Tag>
            )}
            <span>
              {item.code} {item.name}
            </span>
          </span>
          {item.price !== null && (
            <span style={{ color: c.textSecondary }}>
              {isHk ? "HK$" : "¥"}{item.price.toFixed(2)}
            </span>
          )}
        </div>
      ),
    };
  }), [c.textSecondary, currentResults]);

  const handleSelect = useCallback(
    (val: string) => {
      navigate(buildTarget(val));
      clear();
    },
    [buildTarget, clear, navigate]
  );

  // 回车直接跳转（输入6位代码或港股代码时）
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== "Enter") return;
      const code = resolveCode(inputValue);
      if (code) navigate(buildTarget(code));
    },
    [buildTarget, inputValue, navigate, resolveCode]
  );

  return (
    <AutoComplete
      style={{ width: "100%", maxWidth: 500 }}
      options={options}
      value={inputValue}
      onChange={setInputValue}
      onSelect={handleSelect}
      filterOption={false}
      notFoundContent={
        isPending
          ? "搜索中..."
          : isError
            ? <QueryErrorState error={error} onRetry={() => retry()} title="搜索失败" compact />
            : normalizedInput ? "未找到匹配股票，输入6位A股或港股代码后回车可直接跳转" : undefined
      }
    >
      <Input
        size="large"
        aria-label={ariaLabel}
        aria-busy={isPending}
        placeholder="输入股票代码或名称，如 600519、00700 或 贵州茅台、腾讯控股"
        prefix={<SearchOutlined />}
        suffix={isPending ? <span role="status" aria-live="polite" style={{ color: c.textMuted, fontSize: "var(--c-font-sm)" }}>搜索中...</span> : null}
        allowClear
        onKeyDown={handleKeyDown}
      />
    </AutoComplete>
  );
}
