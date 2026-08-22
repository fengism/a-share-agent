import { useCallback, useMemo } from "react";
import { Alert, Card, Row, Col, Table, Typography, Tag, Skeleton, Input, AutoComplete, Space, Empty } from "antd";
import type { ColumnsType } from "antd/es/table";
import { PlusOutlined, StockOutlined } from "@ant-design/icons";
import { useStockCompare } from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import QueryErrorState from "../../components/QueryErrorState";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useStyles } from "../../theme/hooks";
import { formatAmount, formatMarketCap } from "../../utils/format";
import { excludeStockSearchResults } from "../../utils/stockSearch";
import { parseCompareCodes, serializeCompareCodes } from "./compareUrlState";

const { Title, Text } = Typography;

interface CompareTableRow {
  key: string;
  metric: string;
  [stockCode: string]: unknown;
}

export default function ComparePage() {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const { cardStyle, pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();
  const [codesValue, setCodesValue] = useUrlSearchParam("codes", "", { replace: true });
  const selectedCodes = useMemo(() => parseCompareCodes(codesValue), [codesValue]);
  const compareLimitReached = selectedCodes.length >= 5;
  const {
    inputValue: searchText,
    normalizedInput,
    currentResults: searchResults,
    isPending: isSearchPending,
    isError: isSearchError,
    error: searchError,
    retry: retrySearch,
    setInputValue: setSearchText,
    clear: clearSearch,
  } = useStockSearchController();

  const codesParam = serializeCompareCodes(selectedCodes);
  const {
    data: compareData,
    isLoading,
    error: compareQueryError,
    refetch: refetchCompare,
  } = useStockCompare(codesParam);

  const addCode = useCallback((code: string) => {
    if (selectedCodes.length >= 5 || selectedCodes.includes(code)) return;
    setCodesValue(serializeCompareCodes([...selectedCodes, code]));
    clearSearch();
  }, [clearSearch, selectedCodes, setCodesValue]);

  const removeCode = useCallback((code: string) => {
    setCodesValue(serializeCompareCodes(selectedCodes.filter((current) => current !== code)));
  }, [selectedCodes, setCodesValue]);

  const searchOptions = useMemo(() => {
    if (compareLimitReached) return [];
    return excludeStockSearchResults(searchResults, selectedCodes)
      .slice(0, 10)
      .map((stock) => ({
        value: stock.code,
        label: (
          <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
            <span style={{ fontWeight: 500 }}>{stock.name}</span>
            <span style={{ color: c.textSecondary, fontSize: 12 }}>{stock.code}</span>
          </div>
        ),
      }));
  }, [c.textSecondary, compareLimitReached, searchResults, selectedCodes]);

  const hasError = useMemo(() => compareData?.some((item) => item.code === "_error") ?? false, [compareData]);
  const validData = useMemo(() => compareData?.filter((item) => item.code !== "_error") ?? [], [compareData]);

  const columns = useMemo<ColumnsType<CompareTableRow>>(() => [
    { title: "指标", dataIndex: "metric", key: "metric", width: 120, fixed: "left", rowScope: "row" },
    ...validData.map((stock) => ({
      title: stock.name,
      dataIndex: stock.code,
      key: stock.code,
      align: "right" as const,
      width: 150,
      render: (value: unknown, record: CompareTableRow) => {
        if (record.key === "change_pct") {
          return <ChangeValue value={typeof value === "number" ? value : null} fontWeight={500} />;
        }
        return value !== null && value !== undefined
          ? <span style={{ fontWeight: 500 }}>{String(value)}</span>
          : <span style={{ color: c.textSecondary }}>-</span>;
      },
    })),
  ], [c.textSecondary, validData]);

  const tableData = useMemo<CompareTableRow[]>(() => [
    {
      key: "price", metric: "最新价",
      ...Object.fromEntries(validData.map((s) => [s.code, s.price?.toFixed(2) ?? "-"])),
    },
    {
      key: "change_pct", metric: "涨跌幅",
      ...Object.fromEntries(validData.map((s) => [s.code, s.change_pct])),
    },
    {
      key: "market_cap", metric: "总市值",
      ...Object.fromEntries(validData.map((s) => [s.code, formatMarketCap(s.market_cap)])),
    },
    {
      key: "pe_ttm", metric: "PE(TTM)",
      ...Object.fromEntries(validData.map((s) => [s.code, s.pe_ttm?.toFixed(2) ?? "-"])),
    },
    {
      key: "pb", metric: "PB",
      ...Object.fromEntries(validData.map((s) => [s.code, s.pb?.toFixed(2) ?? "-"])),
    },
    {
      key: "ps_ttm", metric: "PS(TTM)",
      ...Object.fromEntries(validData.map((s) => [s.code, s.ps_ttm?.toFixed(2) ?? "-"])),
    },
    {
      key: "turnover_pct", metric: "换手率",
      ...Object.fromEntries(validData.map((s) => [s.code, s.turnover_pct != null ? `${s.turnover_pct.toFixed(2)}%` : "-"])),
    },
    {
      key: "industry", metric: "行业",
      ...Object.fromEntries(validData.map((s) => [s.code, s.industry ?? "-"])),
    },
    {
      key: "revenue", metric: "营业收入",
      ...Object.fromEntries(validData.map((s) => [s.code, formatAmount(s.revenue)])),
    },
    {
      key: "net_profit", metric: "净利润",
      ...Object.fromEntries(validData.map((s) => [s.code, formatAmount(s.net_profit)])),
    },
    {
      key: "roe", metric: "ROE",
      ...Object.fromEntries(validData.map((s) => [s.code, s.roe != null ? `${(s.roe * 100).toFixed(2)}%` : "-"])),
    },
  ], [validData]);

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <div className="u-page-title u-page-title--compact">
          <Title level={3} style={pageTitleStyle}>个股对比</Title>
        </div>
        <Text style={pageDescriptionStyle}>横向对比多只股票的关键财务和估值指标，辅助投资决策。</Text>
      </div>

      {/* Search & selected tags */}
      <Card size="small" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { padding: "14px 18px" } }}>
        <Space orientation="vertical" style={{ width: "100%" }}>
          <AutoComplete
            style={{ width: "100%" }}
            options={searchOptions}
            value={searchText}
            onChange={setSearchText}
            onSelect={(value) => addCode(value)}
            filterOption={false}
            disabled={compareLimitReached}
            notFoundContent={
              isSearchPending
                ? "搜索中..."
                : isSearchError
                  ? <QueryErrorState error={searchError} onRetry={() => retrySearch()} title="搜索失败" compact />
                  : normalizedInput ? "未找到可添加的股票" : null
            }
          >
            <Input
              prefix={<PlusOutlined style={{ color: c.textSecondary }} />}
              placeholder={compareLimitReached ? "最多对比 5 只股票" : "输入股票名称或代码搜索添加..."}
              style={{ height: 40, borderStyle: "dashed" }}
              allowClear
            />
          </AutoComplete>

          {selectedCodes.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>{selectedCodes.length}/5</Text>
              {selectedCodes.map((code) => {
                const stock = validData.find((item) => item.code === code);
                return (
                  <Tag
                    key={code}
                    closable
                    onClose={() => removeCode(code)}
                    color="blue"
                    style={{ fontSize: 13, padding: "2px 10px", borderRadius: 999 }}
                  >
                    {stock?.name || code} ({code})
                  </Tag>
                );
              })}
            </div>
          )}
        </Space>
      </Card>

      {/* Error message */}
      {hasError && (
        <Alert
          type="warning"
          showIcon
          title={compareData?.find((item) => item.code === "_error")?.name || "对比参数无效"}
          style={{ marginBottom: 12 }}
        />
      )}

      {compareQueryError && validData.length === 0 && selectedCodes.length > 0 && (
        <Card size="small" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { padding: 16 } }}>
          <QueryErrorState
            error={compareQueryError}
            onRetry={() => refetchCompare()}
            title="股票对比数据加载失败"
          />
        </Card>
      )}

      {/* Loading */}
      {isLoading && validData.length === 0 && selectedCodes.length > 0 && (
        <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
          {selectedCodes.map((code) => (
            <Col key={code} xs={24} sm={12} md={8} lg={6}>
              <Card size="small" style={cardStyle}>
                <Skeleton active title={{ width: "45%" }} paragraph={{ rows: 4 }} />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Comparison cards */}
      {validData.length > 0 && (
        <>
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {validData.map((stock) => (
              <Col key={stock.code} xs={24} sm={12} md={8} lg={6}>
                <Card
                  size="small"
                  style={{
                    ...cardStyle,
                    borderTop: `3px solid ${c.primary}55`,
                    height: "100%",
                  }}
                  styles={{ body: { padding: "14px 16px" } }}
                >
                  <div style={{ fontWeight: 700, fontSize: 15, color: c.textPrimary, marginBottom: 2 }}>{stock.name}</div>
                  <div style={{ fontSize: 12, color: c.textSecondary, marginBottom: 10 }}>{stock.code}</div>
                  {isNarrow ? (
                    <ResponsiveMetricGrid
                      items={[
                        { key: "price", label: "最新价", value: stock.price?.toFixed(2) ?? "-" },
                        {
                          key: "change",
                          label: "涨跌幅",
                          value: <ChangeValue value={stock.change_pct} fontWeight={500} />,
                        },
                        { key: "market-cap", label: "总市值", value: formatMarketCap(stock.market_cap) },
                        { key: "pe", label: "PE(TTM)", value: stock.pe_ttm?.toFixed(2) ?? "-" },
                        { key: "pb", label: "PB", value: stock.pb?.toFixed(2) ?? "-" },
                        { key: "ps", label: "PS(TTM)", value: stock.ps_ttm?.toFixed(2) ?? "-" },
                        { key: "turnover", label: "换手率", value: stock.turnover_pct == null ? "-" : `${stock.turnover_pct.toFixed(2)}%` },
                        { key: "industry", label: "行业", value: stock.industry ?? "-" },
                        { key: "revenue", label: "营业收入", value: formatAmount(stock.revenue) },
                        { key: "net-profit", label: "净利润", value: formatAmount(stock.net_profit) },
                        { key: "roe", label: "ROE", value: stock.roe == null ? "-" : `${(stock.roe * 100).toFixed(2)}%` },
                      ]}
                    />
                  ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px", fontSize: 12 }}>
                    <span style={{ color: c.textSecondary }}>最新价</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{stock.price?.toFixed(2) ?? "-"}</span>
                    <span style={{ color: c.textSecondary }}>涨跌幅</span>
                    <ChangeValue value={stock.change_pct} fontWeight={600} style={{ textAlign: "right" }} />
                    <span style={{ color: c.textSecondary }}>PE(TTM)</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{stock.pe_ttm?.toFixed(2) ?? "-"}</span>
                    <span style={{ color: c.textSecondary }}>PB</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{stock.pb?.toFixed(2) ?? "-"}</span>
                    <span style={{ color: c.textSecondary }}>总市值</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{formatMarketCap(stock.market_cap)}</span>
                    <span style={{ color: c.textSecondary }}>行业</span>
                    <span style={{ textAlign: "right", color: c.textPrimary }}>{stock.industry ?? "-"}</span>
                    </div>
                  )}
                </Card>
              </Col>
            ))}
          </Row>

          {/* Comparison table */}
          {!isNarrow && (
            <Card
              size="small"
              title={<span style={{ fontWeight: 600 }}>指标对比</span>}
              style={cardStyle}
              styles={{ body: { padding: 0 } }}
            >
              <Table
                dataSource={tableData}
                columns={columns}
                rowKey="key"
                pagination={false}
                size="small"
                scroll={{ x: validData.length * 150 + 150 }}
                bordered
              />
            </Card>
          )}
        </>
      )}

      {/* Empty state */}
      {!isLoading && !compareQueryError && validData.length === 0 && !hasError && (
        <Card size="small" style={cardStyle} styles={{ body: { padding: "60px 20px" } }}>
          <Empty
            image={<StockOutlined style={{ fontSize: 48, color: c.textSecondary }} />}
            description={(
              <span style={{ color: c.textSecondary }}>
                {selectedCodes.length > 0 ? "暂无可用对比数据，请调整股票" : "搜索并添加想要对比的股票"}
              </span>
            )}
          />
        </Card>
      )}
    </div>
  );
}
