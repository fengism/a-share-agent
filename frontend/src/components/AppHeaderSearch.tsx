import { useCallback, useEffect, useMemo, useRef } from "react";
import { AutoComplete, Input, Tag, type InputRef } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useStockSearchController } from "../hooks/useStockSearchController";
import { useColors, useTokens } from "../styles/ui";
import { buildStockProfileUrl } from "../utils/stockLinks";
import QueryErrorState from "./QueryErrorState";

interface AppHeaderSearchProps {
  isMobile: boolean;
  autoFocus?: boolean;
}

export default function AppHeaderSearch({ isMobile, autoFocus = false }: AppHeaderSearchProps) {
  const inputRef = useRef<InputRef>(null);
  const navigate = useNavigate();
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
  const colors = useColors();
  const tokens = useTokens();

  // Global Cmd+K / Ctrl+K and '/' shortcut listener
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      const activeTag = document.activeElement?.tagName.toLowerCase();
      const isInputActive = activeTag === "input" || activeTag === "textarea" || (document.activeElement as HTMLElement)?.isContentEditable;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      } else if (e.key === "/" && !isInputActive && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  const searchOptions = useMemo(() => currentResults.map((item) => {
    const isHk = item.market === "hk" || /^\d{5}$/.test(item.code);
    return {
      value: item.code,
      label: (
        <span style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: tokens.space[3] }}>
          <span style={{ display: "flex", alignItems: "center", gap: tokens.space[2], minWidth: 0 }}>
            {isHk && (
              <Tag color="blue" style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                港股
              </Tag>
            )}
            <span style={{ color: colors.primary, fontWeight: Number(tokens.weight.semibold), fontSize: tokens.font.md, fontFamily: "var(--c-font-mono)" }}>{item.code}</span>
            <span style={{ color: colors.textPrimary, fontSize: tokens.font.md, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {item.name}
            </span>
          </span>
          {!isMobile && item.price != null && (
            <span style={{
              fontSize: tokens.font.sm,
              fontWeight: Number(tokens.weight.medium),
              flexShrink: 0,
              color: item.change_pct != null
                ? (item.change_pct > 0 ? colors.up : item.change_pct < 0 ? colors.down : colors.textSecondary)
                : colors.textSecondary,
            }}>
              {isHk ? "HK$" : "¥"}{item.price.toFixed(2)}
              {item.change_pct != null && (
                <span style={{ marginLeft: tokens.space[1] }}>{item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%</span>
              )}
            </span>
          )}
        </span>
      ),
    };
  }), [colors, tokens, currentResults, isMobile]);

  const handleSelect = useCallback((code: string) => {
    navigate(buildStockProfileUrl(code));
    clear();
  }, [clear, navigate]);

  const handleSearchSubmit = useCallback((value: string) => {
    const code = resolveCode(value);
    if (code) handleSelect(code);
  }, [handleSelect, resolveCode]);

  return (
    <AutoComplete
      style={{ width: "100%", height: 40 }}
      value={inputValue}
      options={searchOptions}
      onChange={setInputValue}
      onSelect={handleSelect}
      filterOption={false}
      notFoundContent={
        isPending
          ? "搜索中..."
          : isError
            ? <QueryErrorState error={error} onRetry={() => retry()} title="搜索失败" compact />
            : normalizedInput ? "未找到匹配的股票" : null
      }
    >
      <Input.Search
        ref={inputRef}
        className="app-header-search"
        size="large"
        placeholder={isMobile ? "代码 / 名称" : "输入A股/港股代码或名称 (⌘K / /)"}
        prefix={isMobile ? undefined : <SearchOutlined />}
        allowClear
        enterButton
        autoFocus={autoFocus}
        onSearch={handleSearchSubmit}
        aria-label="搜索股票"
        aria-busy={isPending}
      />
    </AutoComplete>
  );
}
