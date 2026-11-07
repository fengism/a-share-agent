import { useState } from "react";
import { Badge, Button, Card, Col, Row, Space, Tag, Typography } from "antd";
import { DatabaseOutlined, DownOutlined, SyncOutlined, UpOutlined, WarningOutlined } from "@ant-design/icons";
import { useColors } from "../../../styles/ui";
import type { NationalTeamResponse } from "../../../types/stock";
import { formatMarketDateTime } from "../../../utils/marketTime";

const { Text } = Typography;

interface DataStatusPanelProps {
  data?: NationalTeamResponse;
}

export default function NationalTeamDataStatusPanel({
  data,
}: DataStatusPanelProps) {
  const colors = useColors();
  const [expanded, setExpanded] = useState<boolean>(false);

  if (!data) return null;

  const totalEtfs = data.total_etf_count ?? 22;
  const coveredEtfs = data.covered_etf_count ?? 0;
  const coveragePercent = totalEtfs > 0 ? Math.round((coveredEtfs / totalEtfs) * 100) : 0;
  const isComplete = data.summary?.quality === "complete" || coveragePercent >= 90;

  return (
    <Card
      className="national-team-data-status-card"
      size="small"
      data-testid="national-team-data-status-panel"
      style={{
        borderRadius: 8,
        border: "1px dashed var(--c-border)",
        background: "var(--c-bg-subtle, rgba(128, 128, 128, 0.02))",
        marginBottom: 10,
      }}
      styles={{ body: { padding: "4px 10px" } }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Space size={6} align="center">
            <DatabaseOutlined style={{ color: colors.primary }} />
            <Text strong style={{ fontSize: 13 }}>数据状态与质量监控</Text>
          </Space>

          <Space size={6}>
            <Badge
              status={isComplete ? "success" : "warning"}
              text={
                <span style={{ fontSize: 12, fontWeight: 500 }}>
                  覆盖率 {coveragePercent}% ({coveredEtfs}/{totalEtfs} 只)
                </span>
              }
            />
            <Tag color={isComplete ? "blue" : "gold"} style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
              {isComplete ? "数据完整" : "部分覆盖"}
            </Tag>
          </Space>

          <span style={{ fontSize: 11, color: colors.textSecondary }}>
            业务日期：<strong style={{ fontFamily: "var(--c-font-mono)", color: colors.textPrimary }}>{data.as_of_date || "-"}</strong>
          </span>

          {data.calendar_degraded && (
            <Tag color="warning" icon={<WarningOutlined />} style={{ fontSize: 10, margin: 0 }}>
              交易日历降级
            </Tag>
          )}

          {data.refreshing && (
            <Tag color="processing" icon={<SyncOutlined spin />} style={{ fontSize: 10, margin: 0 }}>
              后台刷新中
            </Tag>
          )}

          {data.partial && (
            <Tag color="orange" style={{ fontSize: 10, margin: 0 }}>
              部分数据
            </Tag>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Button
            size="small"
            type="link"
            onClick={() => setExpanded(!expanded)}
            style={{ padding: 0, fontSize: 12 }}
          >
            {expanded ? <>收起口径说明 <UpOutlined style={{ fontSize: 10 }} /></> : <>查看口径与数据源 <DownOutlined style={{ fontSize: 10 }} /></>}
          </Button>
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px dashed var(--c-border)", fontSize: 12 }}>
          <Row gutter={[16, 12]}>
            <Col xs={24} md={12}>
              <div style={{ padding: "8px 10px", borderRadius: 6, background: "var(--c-bg-layout)" }}>
                <Text strong style={{ fontSize: 12, display: "block", marginBottom: 4 }}>数据源分层说明：</Text>
                <ul style={{ margin: 0, paddingLeft: 18, color: colors.textSecondary, fontSize: 11, lineHeight: "1.6" }}>
                  <li><strong>上交所 / 深交所官方接口</strong>：日频 ETF 份额增减（一级市场申购赎回汇总代理）</li>
                  <li><strong>公开行情适配器</strong>：收盘价、日度成交额、基准指数收盘点位</li>
                  <li><strong>采集时间</strong>：{formatMarketDateTime(data.fetched_at)}</li>
                </ul>
              </div>
            </Col>
            <Col xs={24} md={12}>
              <div style={{ padding: "8px 10px", borderRadius: 6, background: "var(--c-bg-layout)" }}>
                <Text strong style={{ fontSize: 12, display: "block", marginBottom: 4 }}>计算口径规范提示：</Text>
                <div style={{ color: colors.textSecondary, fontSize: 11, lineHeight: "1.5" }}>
                  {data.methodology || "ETF 当日份额变动 × 当日收盘价，逐只计算后按指数归集汇总。"}
                  <div style={{ marginTop: 4, color: "#faad14" }}>
                    注意：二级市场成交额不等于全市场真实净流入；份额变化包含各类公私募、保险与散户申赎，非中央汇金真实持仓。
                  </div>
                </div>
              </div>
            </Col>
          </Row>
        </div>
      )}
    </Card>
  );
}
