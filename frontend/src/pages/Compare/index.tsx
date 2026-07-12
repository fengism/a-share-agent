import { useState, useCallback } from "react";
import { Card, Row, Col, Table, Typography, Tag, Spin, Input, AutoComplete, Space, Empty } from "antd";
import { PlusOutlined, StockOutlined } from "@ant-design/icons";
import { useStockSearch, useStockCompare } from "../../api/queries";
import { useColors, useStyles } from "../../theme/hooks";
import { formatAmount, formatMarketCap } from "../../utils/format";

const { Title, Text } = Typography;

export default function ComparePage() {
  const c = useColors();
  const { cardStyle, pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");

  const codesParam = selectedCodes.join(",");
  const { data: searchResults } = useStockSearch(searchText);
  const { data: compareData, isLoading } = useStockCompare(codesParam);

  const addCode = useCallback((code: string) => {
    setSelectedCodes((prev) => prev.includes(code) ? prev : [...prev, code]);
    setSearchText("");
  }, []);

  const removeCode = useCallback((code: string) => {
    setSelectedCodes((prev) => prev.filter((c) => c !== code));
  }, []);

  const searchOptions = (searchResults || [])
    .filter((s) => !selectedCodes.includes(s.code))
    .slice(0, 10)
    .map((s) => ({
      value: s.code,
      label: (
        <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
          <span style={{ fontWeight: 500 }}>{s.name}</span>
          <span style={{ color: c.textSecondary, fontSize: 12 }}>{s.code}</span>
        </div>
      ),
    }));

  const hasError = compareData?.some((item) => item.code === "_error");
  const validData = compareData?.filter((item) => item.code !== "_error") || [];

  const columns = [
    { title: "指标", dataIndex: "metric", key: "metric", width: 120, fixed: "left" as const },
    ...validData.map((stock) => ({
      title: stock.name,
      dataIndex: stock.code,
      key: stock.code,
      align: "right" as const,
      width: 150,
      render: (val: unknown) => val !== null && val !== undefined
        ? <span style={{ fontWeight: 500 }}>{String(val)}</span>
        : <span style={{ color: c.textSecondary }}>-</span>,
    })),
  ];

  const tableData = [
    {
      key: "price", metric: "最新价",
      ...Object.fromEntries(validData.map((s) => [s.code, s.price?.toFixed(2) ?? "-"])),
    },
    {
      key: "change_pct", metric: "涨跌幅",
      ...Object.fromEntries(validData.map((s) => [s.code, s.change_pct != null ? `${s.change_pct.toFixed(2)}%` : "-"])),
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
  ];

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>个股对比</Title>
        <Text style={pageDescriptionStyle}>横向对比多只股票的关键财务和估值指标，辅助投资决策。</Text>
      </div>

      {/* Search & selected tags */}
      <Card size="small" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { padding: "14px 18px" } }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <AutoComplete
            style={{ width: "100%" }}
            options={searchOptions}
            value={searchText}
            onChange={setSearchText}
            onSelect={(value) => addCode(value)}
            filterOption={false}
          >
            <Input
              prefix={<PlusOutlined style={{ color: c.textSecondary }} />}
              placeholder="输入股票名称或代码搜索添加..."
              style={{ height: 40, borderStyle: "dashed" }}
              allowClear
            />
          </AutoComplete>

          {selectedCodes.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {selectedCodes.map((code) => {
                const stock = validData.find((s) => s.code === code);
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
        <Text type="danger" style={{ display: "block", marginBottom: 12 }}>{compareData?.find((i) => i.code === "_error")?.name}</Text>
      )}

      {/* Loading */}
      {isLoading && selectedCodes.length > 0 && (
        <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
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
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px", fontSize: 12 }}>
                    <span style={{ color: c.textSecondary }}>最新价</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{stock.price?.toFixed(2) ?? "-"}</span>
                    <span style={{ color: c.textSecondary }}>涨跌幅</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: stock.change_pct != null ? (stock.change_pct >= 0 ? c.up : c.down) : c.textSecondary }}>
                      {stock.change_pct != null ? `${stock.change_pct >= 0 ? "+" : ""}${stock.change_pct.toFixed(2)}%` : "-"}
                    </span>
                    <span style={{ color: c.textSecondary }}>PE(TTM)</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{stock.pe_ttm?.toFixed(2) ?? "-"}</span>
                    <span style={{ color: c.textSecondary }}>PB</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{stock.pb?.toFixed(2) ?? "-"}</span>
                    <span style={{ color: c.textSecondary }}>总市值</span>
                    <span style={{ fontWeight: 600, textAlign: "right", color: c.textPrimary }}>{formatMarketCap(stock.market_cap)}</span>
                    <span style={{ color: c.textSecondary }}>行业</span>
                    <span style={{ textAlign: "right", color: c.textPrimary }}>{stock.industry ?? "-"}</span>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          {/* Comparison table */}
          <Card
            size="small"
            title={<span style={{ fontWeight: 600 }}>指标对比</span>}
            style={cardStyle}
            styles={{ body: { padding: 0 } }}
          >
            <Table
              dataSource={tableData}
              columns={columns}
              pagination={false}
              size="small"
              scroll={{ x: validData.length * 150 + 150 }}
              bordered
            />
          </Card>
        </>
      )}

      {/* Empty state */}
      {!isLoading && validData.length === 0 && !hasError && (
        <Card size="small" style={cardStyle} styles={{ body: { padding: "60px 20px" } }}>
          <Empty
            image={<StockOutlined style={{ fontSize: 48, color: c.textSecondary }} />}
            description={<span style={{ color: c.textSecondary }}>搜索并添加想要对比的股票</span>}
          />
        </Card>
      )}
    </div>
  );
}
