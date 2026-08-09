import { useCallback, useMemo } from "react";
import { AutoComplete, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import QueryErrorState from "../../components/QueryErrorState";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import { useColors } from "../../styles/ui";
import { useNavigate } from "react-router-dom";

export default function SearchBar() {
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

  const options = useMemo(() => currentResults.map((item) => ({
    value: item.code,
    label: (
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span>
          {item.code} {item.name}
        </span>
        {item.price !== null && (
          <span style={{ color: c.textSecondary }}>¥{item.price.toFixed(2)}</span>
        )}
      </div>
    ),
  })), [c.textSecondary, currentResults]);

  const handleSelect = useCallback(
    (val: string) => {
      navigate(`/analysis/${val}`);
      clear();
    },
    [clear, navigate]
  );

  // 回车直接跳转（输入6位代码时）
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== "Enter") return;
      const code = resolveCode(inputValue);
      if (code) navigate(`/analysis/${code}`);
    },
    [inputValue, navigate, resolveCode]
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
            : normalizedInput ? "未找到匹配股票，输入6位代码后回车可直接跳转" : undefined
      }
    >
      <Input
        size="large"
        placeholder="输入股票代码或名称，如 600519 或 贵州茅台"
        prefix={<SearchOutlined />}
        suffix={isPending ? <span style={{ color: c.textMuted, fontSize: 12 }}>搜索中...</span> : null}
        allowClear
        onKeyDown={handleKeyDown}
      />
    </AutoComplete>
  );
}
