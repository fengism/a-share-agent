import { useState } from "react";
import { Badge, Button, Card, Col, Row, Space, Tag, Typography } from "antd";
import { DatabaseOutlined, DownOutlined, SyncOutlined, UpOutlined, WarningOutlined } from "@ant-design/icons";
import type { NationalTeamResponse } from "../../../types/stock";
import { formatMarketDateTime } from "../../../utils/marketTime";

const { Text } = Typography;

interface DataStatusPanelProps {
  data?: NationalTeamResponse;
}

export default function NationalTeamDataStatusPanel({
  data,
}: DataStatusPanelProps) {
  const [expanded, setExpanded] = useState<boolean>(false);

  if (!data) return null;

  const totalEtfs = data.total_etf_count ?? 22;
  const coveredEtfs = data.covered_etf_count ?? 0;
  const coveragePercent = totalEtfs > 0 ? Math.round((coveredEtfs / totalEtfs) * 100) : 0;
  const isComplete = data.summary?.quality === "complete" || coveragePercent >= 90;

  return (
    <Card
      className="national-team-data-status-card nt-data-status-card"
      size="small"
      data-testid="national-team-data-status-panel"
      
      styles={{ body: { padding: "4px 10px" } }}
    >
      <div className="nt-status-header">
        <div className="nt-status-meta">
          <Space size={6} align="center">
            <DatabaseOutlined className="u-text-primary" />
            <Text strong className="u-text-md">数据状态与质量监控</Text>
          </Space>

          <Space size={6}>
            <Badge
              status={isComplete ? "success" : "warning"}
              text={
                <span className="nt-status-label">
                  覆盖率 {coveragePercent}% ({coveredEtfs}/{totalEtfs} 只)
                </span>
              }
            />
            <Tag color={isComplete ? "blue" : "gold"} className="nt-status-tag">
              {isComplete ? "数据完整" : "部分覆盖"}
            </Tag>
          </Space>

          <span className="u-text-xs u-text-secondary">
            业务日期：<strong className="nt-status-strong">{data.as_of_date || "-"}</strong>
          </span>

          {data.calendar_degraded && (
            <Tag color="warning" icon={<WarningOutlined />} className="nt-status-tag--plain">
              交易日历降级
            </Tag>
          )}

          {data.refreshing && (
            <Tag color="processing" icon={<SyncOutlined spin />} className="nt-status-tag--plain">
              后台刷新中
            </Tag>
          )}

          {data.partial && (
            <Tag color="orange" className="nt-status-tag--plain">
              部分数据
            </Tag>
          )}
        </div>

        <div className="nt-status-inline">
          <Button
            size="small"
            type="link"
            onClick={() => setExpanded(!expanded)}
            className="nt-status-link"
          >
            {expanded ? <>收起口径说明 <UpOutlined className="nt-status-icon" /></> : <>查看口径与数据源 <DownOutlined className="nt-status-icon" /></>}
          </Button>
        </div>
      </div>

      {expanded && (
        <div className="nt-status-details">
          <Row gutter={[16, 12]}>
            <Col xs={24} md={12}>
              <div className="nt-status-block">
                <Text strong className="nt-status-block-title">数据源分层说明：</Text>
                <ul className="nt-status-list">
                  <li><strong>上交所 / 深交所官方接口</strong>：日频 ETF 份额增减（一级市场申购赎回汇总代理）</li>
                  <li><strong>公开行情适配器</strong>：收盘价、日度成交额、基准指数收盘点位</li>
                  <li><strong>采集时间</strong>：{formatMarketDateTime(data.fetched_at)}</li>
                </ul>
              </div>
            </Col>
            <Col xs={24} md={12}>
              <div className="nt-status-block">
                <Text strong className="nt-status-block-title">计算口径规范提示：</Text>
                <div className="nt-status-text">
                  {data.methodology || "ETF 当日份额变动 × 当日收盘价，逐只计算后按指数归集汇总。"}
                  <div className="nt-status-warning">
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
