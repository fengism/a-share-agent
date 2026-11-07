import React from "react";
import { Card, Checkbox, Pagination, Tag, Button, Empty, Tooltip, Space } from "antd";
import { PlusOutlined, RobotOutlined, LineChartOutlined, CheckOutlined, EyeOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ScreenerItem, ScreenerResult } from "../../types/stock";
import ChangeValue from "../../components/ChangeValue";
import StockWorkspaceDrawer from "../../components/StockWorkspaceDrawer";
import { buildStockProfileUrl } from "../../utils/stockLinks";
import "./screener-card-list.css";

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
  const navigate = useNavigate();
  const [addedCodes, setAddedCodes] = React.useState<Set<string>>(new Set());
  const [previewStock, setPreviewStock] = React.useState<{ code: string; name: string } | null>(null);

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
    return <Empty description="无匹配股票，请调整筛选条件" className="screener-card-list__empty" />;
  }

  return (
    <div className="screener-card-list__container">
      {items.map((record) => {
        const isSelected = selectedCodes.includes(record.code);
        const isAdded = addedCodes.has(record.code);

        return (
          <Card
            key={record.code}
            size="small"
            className={`screener-card-list__card ${isSelected ? "screener-card-list__card--selected" : ""}`}
            styles={{ body: { padding: "var(--c-pad-inset, 7px 12px)" } }}
          >
            {/* 卡片头部：勾选、名称、代码、异动 */}
            <div className="screener-card-list__header">
              <div className="screener-card-list__title-row">
                <Checkbox
                  checked={isSelected}
                  disabled={!isSelected && selectedCodes.length >= 10}
                  onChange={() => handleToggleSelect(record.code)}
                />
                <div>
                  <div className="screener-card-list__stock-info">
                    <span
                      className="screener-card-list__stock-name"
                      onClick={() => navigate(buildStockProfileUrl(record.code))}
                    >
                      {record.name}
                    </span>
                    <span className="screener-card-list__stock-code">
                      {record.code}
                    </span>
                    {record.board || record.exchange ? (
                      <Tag className="screener-card-list__badge">
                        {record.board || record.exchange}
                      </Tag>
                    ) : null}
                    {record.composite_score != null && (
                      <Tag
                        color={record.composite_score >= 80 ? "gold" : record.composite_score >= 65 ? "blue" : undefined}
                        className="screener-card-list__score-tag"
                      >
                        {record.composite_score.toFixed(0)}分
                      </Tag>
                    )}
                  </div>
                  {/* 异动标签 */}
                  <div className="screener-card-list__tag-list">
                    {record.change_pct != null && record.change_pct >= 9.8 && (
                      <Tag color="red" className="screener-card-list__signal-tag">
                        涨停
                      </Tag>
                    )}
                    {record.change_pct != null && record.change_pct <= -9.8 && (
                      <Tag color="green" className="screener-card-list__signal-tag">
                        跌停
                      </Tag>
                    )}
                    {record.turnover_pct != null && record.turnover_pct >= 8 && (
                      <Tag color="warning" className="screener-card-list__signal-tag">
                        高换手
                      </Tag>
                    )}
                    {record.volume_ratio != null && record.volume_ratio >= 2.0 && (
                      <Tag color="purple" className="screener-card-list__signal-tag">
                        放量
                      </Tag>
                    )}
                    {record.is_broken_net && (
                      <Tag color="cyan" className="screener-card-list__signal-tag">
                        破净
                      </Tag>
                    )}
                  </div>
                </div>
              </div>

              {/* 现价与涨跌幅 */}
              <div className="screener-card-list__price-col">
                <div className="screener-card-list__price">
                  {record.price?.toFixed(2) ?? "-"}
                </div>
                <div className="screener-card-list__change">
                  <ChangeValue value={record.change_pct} fontWeight={600} />
                </div>
              </div>
            </div>

            {/* 卡片核心指标网格 */}
            <div className="screener-card-list__metric-grid">
              <div>
                <span className="screener-card-list__metric-label">PE(TTM): </span>
                <span className="screener-card-list__metric-value">{record.pe_ttm?.toFixed(1) ?? "-"}</span>
              </div>
              <div>
                <span className="screener-card-list__metric-label">PB: </span>
                <span className="screener-card-list__metric-value">{record.pb?.toFixed(2) ?? "-"}</span>
              </div>
              <div>
                <span className="screener-card-list__metric-label">市值: </span>
                <span className="screener-card-list__metric-value">
                  {record.market_cap == null
                    ? "-"
                    : record.market_cap >= 10000
                      ? `${(record.market_cap / 10000).toFixed(1)}万`
                      : `${record.market_cap.toFixed(0)}亿`}
                </span>
              </div>
              <div>
                <span className="screener-card-list__metric-label">换手: </span>
                <span className="screener-card-list__metric-value">
                  {record.turnover_pct != null ? `${record.turnover_pct.toFixed(1)}%` : "-"}
                </span>
              </div>
            </div>

            {/* 概念与操作按钮 */}
            <div className="screener-card-list__footer">
              <div className="screener-card-list__concepts">
                <span>{record.second_industry?.name || record.first_industry?.name || "未知行业"}</span>
                {record.concepts && record.concepts.length > 0 ? (
                  <Tooltip title={record.concepts.join(" · ")}>
                    <Tag className="screener-card-list__concept-tag">
                      {record.concepts[0]}
                      {record.concepts.length > 1 ? ` +${record.concepts.length - 1}` : ""}
                    </Tag>
                  </Tooltip>
                ) : null}
              </div>

              <Space size={6}>
                <Button
                  size="small"
                  icon={isAdded ? <CheckOutlined className="screener-card-list__added-icon" /> : <PlusOutlined />}
                  disabled={isAdded}
                  onClick={() => void handleAddWatchlist(record)}
                >
                  {isAdded ? "已加" : "自选"}
                </Button>
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => setPreviewStock({ code: record.code, name: record.name })}
                >
                  速查
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
        <div className="screener-card-list__pagination-wrap">
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

      {previewStock ? (
        <StockWorkspaceDrawer
          open={Boolean(previewStock)}
          code={previewStock.code}
          name={previewStock.name}
          onClose={() => setPreviewStock(null)}
        />
      ) : null}
    </div>
  );
};

export default ScreenerCardList;
