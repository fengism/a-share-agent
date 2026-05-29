import { useState, useCallback } from "react";
import { AutoComplete, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useStockSearch } from "../../api/queries";
import { useNavigate } from "react-router-dom";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const { data: results = [], isLoading } = useStockSearch(query);
  const navigate = useNavigate();

  const options = results.map((item) => ({
    value: item.code,
    label: (
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span>
          {item.code} {item.name}
        </span>
        {item.price !== null && (
          <span style={{ color: "#333" }}>¥{item.price.toFixed(2)}</span>
        )}
      </div>
    ),
  }));

  const handleSearch = useCallback((val: string) => {
    const trimmed = val.trim();
    console.log(`[Search] 输入: "${trimmed}"`);
    setQuery(trimmed);
  }, []);

  const handleSelect = useCallback(
    (val: string) => {
      console.log(`[Search] 选中: ${val}，跳转分析页`);
      navigate(`/analysis/${val}`);
    },
    [navigate]
  );

  // 回车直接跳转（输入6位代码时）
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && query.length === 6 && /^\d{6}$/.test(query)) {
        console.log(`[Search] 回车跳转: ${query}`);
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
        suffix={isLoading ? <span style={{ color: "#999", fontSize: 12 }}>搜索中...</span> : null}
        allowClear
        onKeyDown={handleKeyDown}
      />
    </AutoComplete>
  );
}
