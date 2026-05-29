import { Card, Typography, Tag, Empty, Spin } from "antd";
import { SearchOutlined, RobotOutlined, HistoryOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import SearchBar from "../Dashboard/SearchBar";
import { useAllAnalysisHistory } from "../../api/queries";
import type { AnalysisHistoryItem } from "../../types/stock";

const { Title, Paragraph } = Typography;

function signalColor(signal: string | null) {
  if (signal === "strong_buy" || signal === "buy") return "#ef4444";
  if (signal === "strong_sell" || signal === "sell") return "#22c55e";
  return "#e5e7eb";
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
  const navigate = useNavigate();
  const { data: allHistory, isLoading } = useAllAnalysisHistory();

  const grouped = allHistory ? groupByStock(allHistory) : {};

  return (
    <div style={{ display: "flex", gap: 20, minHeight: "calc(100vh - 120px)" }}>
      {/* Left: History Panel */}
      <div style={{ width: 320, flexShrink: 0 }}>
        <Card
          style={{ background: "#111827", border: "1px solid #1e293b", borderRadius: 10, height: "100%" }}
          styles={{ body: { padding: 0 } }}
        >
          <div style={{ padding: "14px 16px 10px", borderBottom: "1px solid #1e293b" }}>
            <span style={{ fontWeight: 600, color: "#e5e7eb", fontSize: 14 }}>
              <HistoryOutlined style={{ marginRight: 8, color: "#3b82f6" }} />
              分析历史
            </span>
          </div>
          <div style={{ maxHeight: "calc(100vh - 220px)", overflowY: "auto", padding: "8px 10px" }}>
            {isLoading ? (
              <div style={{ textAlign: "center", padding: 24 }}><Spin /></div>
            ) : Object.keys(grouped).length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<span style={{ color: "#9ca3af", fontSize: 12 }}>暂无分析记录</span>}
                style={{ marginTop: 40 }}
              />
            ) : (
              Object.entries(grouped).map(([code, items]) => (
                <div key={code} style={{ marginBottom: 10 }}>
                  {items.map((item) => {
                    const dateStr = item.analysis_date;
                    const displayDate = `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
                    const sc = signalColor(item.signal);
                    return (
                      <div
                        key={`${code}-${dateStr}`}
                        onClick={() => navigate(`/analysis/${code}`)}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "8px 10px",
                          marginBottom: 4,
                          background: "#0f1720",
                          border: "1px solid #1e293b",
                          borderRadius: 8,
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#3b82f6"; e.currentTarget.style.background = "#1a2840"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#1e293b"; e.currentTarget.style.background = "#0f1720"; }}
                      >
                        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontSize: 12, color: "#3b82f6", fontFamily: "monospace", fontWeight: 600 }}>{item.stock_code}</span>
                            <span style={{ fontSize: 12, color: "#e5e7eb", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.stock_name}</span>
                          </div>
                          <span style={{ fontSize: 11, color: "#9ca3af" }}>{displayDate}</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                          {item.overall_rating != null && (
                            <span style={{ fontSize: 12, fontWeight: 700, color: item.overall_rating >= 7 ? "#ef4444" : item.overall_rating <= 3 ? "#22c55e" : "#e5e7eb" }}>
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
            <RobotOutlined style={{ color: "#6366f1", marginRight: 12 }} />
            <SearchOutlined style={{ color: "#3b82f6" }} />
          </div>
          <Title level={2} style={{ margin: 0, color: "#e5e7eb" }}>
            AI 智能分析
          </Title>
          <Paragraph type="secondary" style={{ fontSize: 16, marginTop: 8 }}>
            输入股票代码或名称，进入独立分析页，查看基本面、技术面、情绪面与 AI 结论
          </Paragraph>
        </div>

        <Card
          style={{
            borderRadius: 12,
            boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
            padding: "8px 0",
            width: "100%",
            maxWidth: 560,
          }}
          styles={{ body: { padding: "24px 24px 16px", display: "flex", justifyContent: "center" } }}
        >
          <SearchBar />
        </Card>
      </div>
    </div>
  );
}
