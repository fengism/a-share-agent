import React from "react";
import { Card, Checkbox, Pagination, Tag, Button, Empty, Tooltip, Space } from "antd";
import { PlusOutlined, RobotOutlined, LineChartOutlined, CheckOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ScreenerItem, ScreenerResult } from "../../types/stock";
import ChangeValue from "../../components/ChangeValue";
import { buildStockProfileUrl } from "../../utils/stockLinks";
import * as uiStyles from "../../styles/ui";

const DEFAULT_COLORS = {
  primary: "#1677ff",
  textPrimary: "rgba(0, 0, 0, 0.88)",
  textMuted: "rgba(0, 0, 0, 0.45)",
  up: "#f5222d",
  down: "#52c41a",
};

interface ScreenerCardListProps {
  data: ScreenerResult | undefined;
  isLoading: boolean;
  selectedCodes: string[];
  onSelectedCodesChange: (codes: string[]) => void;
  onPageChange: (page: number, pageSize: number) => void;
  onAddWatchlist?: (stock: ScreenerItem) => Promise<void> | void;
}

export const ScreenerCardList: React.FC<ScreenerCardListProps> = ({
  data,
  isLoading,
  selectedCodes,
  onSelectedCodesChange,
  onPageChange,
  onAddWatchlist,
}) => {
  const c = typeof uiStyles.useColors === "function" ? uiStyles.useColors() : DEFAULT_COLORS;
  const navigate = useNavigate();
  const [addedCodes, setAddedCodes] = React.useState<Set<string>>(new Set());

  const items = data?.items ?? [];

  const handleToggleSelect = (code: string) => {
    if (selectedCodes.includes(code)) {
      onSelectedCodesChange(selectedCodes.filter((c) => c !== code));
    } else {
      if (selectedCodes.length < 10) {
        onSelectedCodesChange([...selectedCodes, code]);
      }
    }
  };

  const handleAddWatchlist = async (record: ScreenerItem) => {
    try {
      if (onAddWatchlist) {
        await onAddWatchlist(record);
      }
      setAddedCodes((prev) => new Set(prev).add(record.code));
    } catch {
      // handled
    }
  };

  const handleAiDiagnose = (record: ScreenerItem) => {
    const prompt = `请对股票 ${record.name}（代码：${record.code}）进行深度量化与基本面体检，评估其估值水平（当前 PE: ${record.pe_ttm ?? "未知"}，PB: ${record.pb ?? "未知"}）、行业竞争壁垒、技术走势及潜在投资风险。`;
    navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  if (!isLoading && items.length === 0) {
    return <Empty description="无匹配股票，请调整筛选条件" style={{ margin: "32px 0" }} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {items.map((record) => {
        const isSelected = selectedCodes.includes(record.code);
        const isAdded = addedCodes.has(record.code);

        return (
          <Card
            key={record.code}
            size="small"
            style={{
              borderRadius: 8,
              border: isSelected ? `1px solid ${c.primary}` : "1px solid var(--c-border, #f0f0f0)",
              background: isSelected ? "var(--c-fill-quaternary, rgba(22, 119, 255, 0.02))" : undefined,
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
            }}
            styles={{ body: { padding: "var(--c-pad-inset, 7px 12px)" } }}
          >
            {/* 卡片头部：勾选、名称、代码、异动 */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Checkbox
                  checked={isSelected}
                  disabled={!isSelected && selectedCodes.length >= 10}
                  onChange={() => handleToggleSelect(record.code)}
                />
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <span
                      style={{
                        fontWeight: 600,
                        fontSize: 15,
                        color: c.textPrimary,
                        cursor: "pointer",
                      }}
                      onClick={() => navigate(buildStockProfileUrl(record.code))}
                    >
                      {record.name}
                    </span>
                    <span style={{ fontSize: 12, color: c.textMuted, fontFamily: "var(--c-font-mono)" }}>
                      {record.code}
                    </span>
                    {record.board || record.exchange ? (
                      <Tag style={{ margin: 0, fontSize: 10, lineHeight: "16px", padding: "0 4px" }}>
                        {record.board || record.exchange}
                      </Tag>
                    ) : null}
                    {record.composite_score != null && (
                      <Tag
                        color={record.composite_score >= 80 ? "gold" : record.composite_score >= 65 ? "blue" : undefined}
                        style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0, fontWeight: 600 }}
                      >
                        {record.composite_score.toFixed(0)}分
                      </Tag>
                    )}
                  </div>
                  {/* 异动标签 */}
                  <div style={{ display: "flex", gap: 4, marginTop: 4, flexWrap: "wrap" }}>
                    {record.change_pct != null && record.change_pct >= 9.8 && (
                      <Tag color="error" style={{ margin: 0, fontSize: 10, lineHeight: "14px", padding: "0 4px" }}>
                        涨停
                      </Tag>
                    )}
                    {record.change_pct != null && record.change_pct <= -9.8 && (
                      <Tag color="success" style={{ margin: 0, fontSize: 10, lineHeight: "14px", padding: "0 4px" }}>
                        跌停
                      </Tag>
                    )}
                    {record.turnover_pct != null && record.turnover_pct >= 8 && (
                      <Tag color="warning" style={{ margin: 0, fontSize: 10, lineHeight: "14px", padding: "0 4px" }}>
                        高换手
                      </Tag>
                    )}
                    {record.volume_ratio != null && record.volume_ratio >= 2.0 && (
                      <Tag color="purple" style={{ margin: 0, fontSize: 10, lineHeight: "14px", padding: "0 4px" }}>
                        放量
                      </Tag>
                    )}
                    {record.is_broken_net && (
                      <Tag color="cyan" style={{ margin: 0, fontSize: 10, lineHeight: "14px", padding: "0 4px" }}>
                        破净
                      </Tag>
                    )}
                  </div>
                </div>
              </div>

              {/* 现价与涨跌幅 */}
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--c-font-mono)", color: c.textPrimary }}>
                  {record.price?.toFixed(2) ?? "-"}
                </div>
                <div style={{ fontSize: 12 }}>
                  <ChangeValue value={record.change_pct} fontWeight={600} />
                </div>
              </div>
            </div>

            {/* 卡片核心指标网格 */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: "6px 8px",
                background: "var(--c-fill-quaternary, rgba(0, 0, 0, 0.02))",
                padding: "6px 8px",
                borderRadius: 6,
                fontSize: 11,
                marginBottom: 8,
              }}
            >
              <div>
                <span style={{ color: c.textMuted }}>PE(TTM): </span>
                <span style={{ fontFamily: "var(--c-font-mono)", color: c.textPrimary }}>{record.pe_ttm?.toFixed(1) ?? "-"}</span>
              </div>
              <div>
                <span style={{ color: c.textMuted }}>PB: </span>
                <span style={{ fontFamily: "var(--c-font-mono)", color: c.textPrimary }}>{record.pb?.toFixed(2) ?? "-"}</span>
              </div>
              <div>
                <span style={{ color: c.textMuted }}>市值: </span>
                <span style={{ fontFamily: "var(--c-font-mono)", color: c.textPrimary }}>
                  {record.market_cap == null
                    ? "-"
                    : record.market_cap >= 10000
                      ? `${(record.market_cap / 10000).toFixed(1)}万`
                      : `${record.market_cap.toFixed(0)}亿`}
                </span>
              </div>
              <div>
                <span style={{ color: c.textMuted }}>换手: </span>
                <span style={{ fontFamily: "var(--c-font-mono)", color: c.textPrimary }}>
                  {record.turnover_pct != null ? `${record.turnover_pct.toFixed(1)}%` : "-"}
                </span>
              </div>
            </div>

            {/* 概念与操作按钮 */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
              <div style={{ fontSize: 11, color: c.textMuted, display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                <span>{record.second_industry?.name || record.first_industry?.name || "未知行业"}</span>
                {record.concepts && record.concepts.length > 0 ? (
                  <Tooltip title={record.concepts.join(" · ")}>
                    <Tag style={{ margin: 0, fontSize: 10, lineHeight: "16px", padding: "0 4px" }}>
                      {record.concepts[0]}
                      {record.concepts.length > 1 ? ` +${record.concepts.length - 1}` : ""}
                    </Tag>
                  </Tooltip>
                ) : null}
              </div>

              <Space size={6}>
                <Button
                  size="small"
                  icon={isAdded ? <CheckOutlined style={{ color: "#52c41a" }} /> : <PlusOutlined />}
                  disabled={isAdded}
                  onClick={() => void handleAddWatchlist(record)}
                >
                  {isAdded ? "已加" : "自选"}
                </Button>
                <Button
                  size="small"
                  type="primary"
                  ghost
                  icon={<RobotOutlined />}
                  onClick={() => handleAiDiagnose(record)}
                >
                  AI 体检
                </Button>
                <Button
                  size="small"
                  icon={<LineChartOutlined />}
                  onClick={() => navigate(buildStockProfileUrl(record.code))}
                >
                  走势
                </Button>
              </Space>
            </div>
          </Card>
        );
      })}

      {/* 紧凑移动端分页 */}
      {data && data.total > 0 && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
          <Pagination
            size="small"
            current={data.page || 1}
            pageSize={data.page_size || 50}
            total={data.total}
            showSizeChanger={false}
            onChange={(page, pageSize) => onPageChange(page, pageSize)}
          />
        </div>
      )}
    </div>
  );
};

export default ScreenerCardList;
