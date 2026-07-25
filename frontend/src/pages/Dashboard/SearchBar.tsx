import { useState, useCallback } from "react";
import { AutoComplete, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useStockSearch } from "../../api/queries";
import { useColors } from "../../styles/ui";
import { useNavigate } from "react-router-dom";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const { data: results = [], isLoading } = useStockSearch(query);
  const navigate = useNavigate();
  const c = useColors();

  const options = results.map((item) => ({
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
  }));

  const handleSearch = useCallback((val: string) => {
    setQuery(val.trim());
  }, []);

  const handleSelect = useCallback(
    (val: string) => {
      navigate(`/analysis/${val}`);
    },
    [navigate]
  );

  // 回车直接跳转（输入6位代码时）
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && query.length === 6 && /^\d{6}$/.test(query)) {
        navigate(`/analysis/${query}`);
      }
    },
    [query, navigate]
  );

  return (
    <AutoComplete
      style={{ width: "100%", maxWidth: 500 }}
      options={options}
      onSearch={handleSearch}
      onSelect={handleSelect}
      notFoundContent={isLoading ? "搜索中..." : query ? "未找到匹配股票，输入6位代码后回车可直接跳转" : undefined}
    >
      <Input
        size="large"
        placeholder="输入股票代码或名称，如 600519 或 贵州茅台"
        prefix={<SearchOutlined />}
        suffix={isLoading ? <span style={{ color: c.textMuted, fontSize: 12 }}>搜索中...</span> : null}
        allowClear
        onKeyDown={handleKeyDown}
      />
    </AutoComplete>
  );
}
