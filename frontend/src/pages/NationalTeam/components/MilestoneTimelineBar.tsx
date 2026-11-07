import { useMemo, useState } from "react";
import { Button, Card, Col, Row, Tag, Typography } from "antd";
import {
  DownOutlined,
  SafetyCertificateOutlined,
  UpOutlined,
} from "@ant-design/icons";
import type { NationalTeamMilestone } from "../../../types/stock";

const { Text } = Typography;

export default function MilestoneTimelineBar({ milestones }: { milestones?: NationalTeamMilestone[] }) {
  const [expanded, setExpanded] = useState(false);
  const items = useMemo(() => milestones ?? [], [milestones]);
  if (!items.length) return null;

  const typeTags: Record<string, { label: string; color: string }> = {
    statement: { label: "官方表态", color: "blue" },
    intervention: { label: "主力扫货", color: "orange" },
    policy: { label: "制度发布", color: "gold" },
    liquidity: { label: "流动性落地", color: "purple" },
  };

  return (
    <Card
      className="national-team-milestone-card"
      size="small"
      data-testid="national-team-milestones"
      styles={{ body: { padding: "var(--c-pad-inset, 7px 12px)" } }}
    >
      <div className={`national-team-milestone__head${expanded ? " national-team-milestone__head--expanded" : ""}`}>
        <div className="national-team-milestone__head-left">
          <SafetyCertificateOutlined className="national-team-milestone__icon" />
          <span className="national-team-milestone__title">国家队关键政策底救市标尺</span>
          <Text type="secondary" className="national-team-milestone__subtitle">
            历次重要增持公告与流动性托底工具节点
          </Text>
        </div>
        <Button
          type="link"
          size="small"
          className="national-team-milestone__toggle"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <>收起明细 <UpOutlined className="national-team-milestone__caret" /></> : <>查看历次救市节点 <DownOutlined className="national-team-milestone__caret" /></>}
        </Button>
      </div>

      {expanded && (
        <div className="national-team-milestone-list">
          <Row gutter={[10, 10]}>
            {items.map((m) => {
              const meta = typeTags[m.type] || { label: "政策", color: "default" };
              return (
                <Col xs={24} sm={12} lg={8} key={m.date}>
                  <div className="national-team-milestone__item">
                    <div className="national-team-milestone__item-head">
                      <span className="national-team-milestone__date">{m.date}</span>
                      <Tag color={meta.color} className="national-team-milestone__type-tag">
                        {meta.label}
                      </Tag>
                    </div>
                    <div className="national-team-milestone__item-title">{m.title}</div>
                    <Text type="secondary" className="national-team-milestone__desc">
                      {m.description}
                    </Text>
                    {m.index_points && Object.keys(m.index_points).length > 0 && (
                      <div className="national-team-milestone__points">
                        {Object.entries(m.index_points).map(([idx, pts]) => (
                          <Tag key={idx} color="blue" className="national-team-milestone__point-tag">
                            {idx}: {pts}
                          </Tag>
                        ))}
                      </div>
                    )}
                  </div>
                </Col>
              );
            })}
          </Row>
        </div>
      )}
    </Card>
  );
}
