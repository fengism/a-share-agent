import { Card, Skeleton, Row, Col } from "antd";
import { useColors, useTokens } from "../../theme/hooks";

export default function SkeletonAIConclusion() {
  const c = useColors();
  const t = useTokens();

  return (
    <Card
      size="small"
      title="AI 智能分析"
      style={{
        marginBottom: t.space[4],
        borderRadius: t.radius.lg,
        border: `1px solid ${c.border}`,
        boxShadow: t.shadow.xs,
      }}
      styles={{ body: { padding: `${t.space[5]} ${t.space[6]}` } }}
    >
      <Row gutter={[t.space[6], t.space[4]]}>
        <Col span={8} style={{ textAlign: "center" }}>
          <Skeleton.Avatar active size={80} shape="circle" />
          <Skeleton
            active
            paragraph={{ rows: 2, width: ["60%", "80%"] }}
            title={false}
            style={{ marginTop: t.space[3] }}
          />
        </Col>
        <Col span={16}>
          <Row gutter={t.space[3]}>
            {[1, 2, 3].map((i) => (
              <Col span={8} key={i}>
                <div style={{ padding: t.space[3], background: c.hoverBg, borderRadius: t.radius.md, textAlign: "center" }}>
                  <Skeleton.Avatar active size={48} shape="circle" />
                  <Skeleton
                    active
                    paragraph={false}
                    title={{ width: "60%" }}
                    style={{ marginTop: t.space[1] }}
                  />
                </div>
              </Col>
            ))}
          </Row>
          <Skeleton active paragraph={{ rows: 3 }} style={{ marginTop: t.space[4] }} />
          <Skeleton active paragraph={{ rows: 2 }} style={{ marginTop: t.space[2] }} />
        </Col>
      </Row>
    </Card>
  );
}
