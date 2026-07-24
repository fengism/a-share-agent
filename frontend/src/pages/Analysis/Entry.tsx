import { Card, Typography, Tag, Empty, Spin } from "antd";
import { RobotOutlined, HistoryOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import SearchBar from "../Dashboard/SearchBar";
import { useAllAnalysisHistory } from "../../api/queries";
;
import type { AnalysisHistoryItem } from "../../types/stock";
import { useColors } from "../../styles/ui";

const { Title, Paragraph } = Typography;

function signalColor(c_up: string, c_down: string, c_default: string, signal: string | null) {
  if (signal === "strong_buy" || signal === "buy") return c_up;
  if (signal === "strong_sell" || signal === "sell") return c_down;
  return c_default;
}

function signalLabel(signal: string | null) {
  if (signal === "strong_buy") return "强烈买入";
  if (signal === "buy") return "买入";
  if (signal === "sell") return "卖出";
  if (signal === "strong_sell") return "强烈卖出";
  return "持有";
}

function groupByStock(items: AnalysisHistoryItem[]): Record<string, AnalysisHistoryItem[]> {
  const groups: Record<string, AnalysisHistoryItem[]> = {};
  for (const item of items) {
    const key = item.stock_code;
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  for (const code of Object.keys(groups)) {
    groups[code].sort((a, b) => b.analysis_date.localeCompare(a.analysis_date));
  }
  return groups;
}

export default function AnalysisEntry() {
  const c = useColors();
  const navigate = useNavigate();
  const { data: allHistory, isLoading } = useAllAnalysisHistory();

  const grouped = allHistory ? groupByStock(allHistory) : {};

  return (
    <div className="two-pane" style={{ display: "flex", gap: 20, minHeight: "calc(100vh - 120px)" }}>
      {/* Left: History Panel */}
      <div className="pane-side" style={{ width: 280, flexShrink: 0 }}>
        <Card
          style={{ background: c.cardBg, border: `1px solid ${c.border}`, borderRadius: 10, height: "100%" }}
          styles={{ body: { padding: 0 } }}
        >
          <div style={{ padding: "14px 16px 10px", borderBottom: `1px solid ${c.border}` }}>
            <span style={{ fontWeight: 600, color: c.textPrimary, fontSize: 14 }}>
              <HistoryOutlined style={{ marginRight: 8, color: c.primary }} />
              分析历史
            </span>
          </div>
          <div style={{ maxHeight: "calc(100vh - 220px)", overflowY: "auto", padding: "8px 10px" }}>
            {isLoading ? (
              <div style={{ textAlign: "center", padding: 24 }}><Spin /></div>
            ) : Object.keys(grouped).length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<span style={{ color: c.textSecondary, fontSize: 12 }}>暂无分析记录</span>}
                style={{ marginTop: 40 }}
              />
            ) : (
              Object.entries(grouped).map(([code, items]) => (
                <div key={code} style={{ marginBottom: 10 }}>
                  {items.map((item) => {
                    const dateStr = item.analysis_date;
                    const displayDate = `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
                    const sc = signalColor(c.up, c.down, c.textPrimary, item.signal);
                    return (
                      <div
                        key={`${code}-${dateStr}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => navigate(`/analysis/${code}`)}
                        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate(`/analysis/${code}`); } }}
                        className="hover-row"
                        style={{
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "8px 10px", marginBottom: 4,
                          borderRadius: 8, cursor: "pointer",
                        }}
                      >
                        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontSize: 12, color: c.primary, fontFamily: "monospace", fontWeight: 600 }}>{item.stock_code}</span>
                            <span style={{ fontSize: 12, color: c.textPrimary, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.stock_name}</span>
                          </div>
                          <span style={{ fontSize: 11, color: c.textSecondary }}>{displayDate}</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                          {item.overall_rating != null && (
                            <span style={{ fontSize: 12, fontWeight: 700, color: item.overall_rating >= 7 ? c.up : item.overall_rating <= 3 ? c.down : c.textPrimary }}>
                              {item.overall_rating}
                            </span>
                          )}
                          {item.signal && (
                            <Tag style={{ color: sc, background: "transparent", border: `1px solid ${sc}33`, fontSize: 11, margin: 0, padding: "0 4px" }}>
                              {signalLabel(item.signal)}
                            </Tag>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Right: Search / Landing */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 24px" }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>
            <RobotOutlined style={{ color: c.accent, marginRight: 12 }} />
          </div>
          <Title level={2} style={{ margin: 0, color: c.textPrimary }}>AI 智能分析</Title>
          <Paragraph style={{ fontSize: 16, marginTop: 8, color: c.textSecondary }}>
            输入股票代码或名称，进入独立分析页，查看基本面、技术面、情绪面与 AI 结论
          </Paragraph>
        </div>
        <Card
          style={{
            borderRadius: 10, boxShadow: "0 1px 2px rgba(0,0,0,0.18)",
            padding: "8px 0", width: "100%", maxWidth: 560,
            background: c.cardBg, border: `1px solid ${c.border}`,
          }}
          styles={{ body: { padding: "24px 24px 16px", display: "flex", justifyContent: "center" } }}
        >
          <SearchBar />
        </Card>
      </div>
    </div>
  );
}
