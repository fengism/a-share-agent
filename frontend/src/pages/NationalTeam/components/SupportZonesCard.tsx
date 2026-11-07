import { useMemo } from "react";
import { Card, Col, Row, Tag, Typography } from "antd";
import type { NationalTeamSupportZone } from "../../../types/stock";

const { Text } = Typography;

export default function SupportZonesCard({ supportZones }: { supportZones?: NationalTeamSupportZone[] }) {
  const zones = useMemo(() => supportZones ?? [], [supportZones]);
  if (!zones.length) return null;

  return (
    <Card
      className="national-team-support-zones-card"
      size="small"
      data-testid="national-team-support-zones"
      title={
        <div className="national-team-support-zones__title">
          <span className="national-team-support-zones__title-text">核心指数主力成本中枢与托底点位分布</span>
          <Text type="secondary" className="national-team-support-zones__title-sub">
            按各点位区间正净申购资金加权估算托底密集区
          </Text>
        </div>
      }
    >
      <Row gutter={[12, 12]}>
        {zones.map((zone) => {
          const isBufferPos = (zone.cost_buffer_pct ?? 0) >= 0;
          return (
            <Col xs={24} md={8} key={zone.index_key}>
              <div className="national-team-support-zones__zone">
                <div className="national-team-support-zones__zone-head">
                  <span className="national-team-support-zones__zone-name">{zone.index_name}</span>
                  <Tag color="blue" className="national-team-support-zones__price-tag">
                    当前点位 {zone.current_price ? Math.round(zone.current_price) : "-"}
                  </Tag>
                </div>
                <div className="national-team-support-zones__cost-row">
                  <div>
                    <span className="national-team-support-zones__cost-label">加权平均买入成本：</span>
                    <strong className="national-team-support-zones__cost-value">
                      {zone.weighted_avg_cost ? Math.round(zone.weighted_avg_cost) : "-"} 点
                    </strong>
                  </div>
                  {zone.cost_buffer_pct != null && (
                    <span className={`national-team-support-zones__buffer ${isBufferPos ? "is-up" : "is-down"}`}>
                      安全垫 {isBufferPos ? "+" : ""}{zone.cost_buffer_pct}%
                    </span>
                  )}
                </div>

                <div className="national-team-support-zones__bars">
                  {(zone.zones ?? []).map((z) => (
                    <div key={z.range_label} className="national-team-support-zones__bar-row">
                      <span className="national-team-support-zones__range">{z.range_label}</span>
                      <div className="national-team-support-zones__track">
                        <div
                          className="national-team-support-zones__fill"
                          style={{ width: `${Math.min(100, Math.max(5, z.share_pct))}%` }}
                        />
                      </div>
                      <span className="national-team-support-zones__share">{z.share_pct}%</span>
                      <span className="national-team-support-zones__flow">{z.net_flow_100m}亿</span>
                    </div>
                  ))}
                </div>
              </div>
            </Col>
          );
        })}
      </Row>
    </Card>
  );
}
