import { Card, Skeleton, Row, Col } from "antd";

export default function SkeletonAIConclusion() {
  return (
    <Card
      size="small"
      title="AI 智能分析"
      style={{
        marginBottom: 16,
        borderRadius: 10,
        border: "none",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
      }}
      styles={{ body: { padding: "20px 24px" } }}
    >
      <Row gutter={[24, 16]}>
        <Col span={8} style={{ textAlign: "center" }}>
          <Skeleton.Avatar active size={80} shape="circle" />
          <Skeleton
            active
            paragraph={{ rows: 2, width: ["60%", "80%"] }}
            title={false}
            style={{ marginTop: 12 }}
          />
        </Col>
        <Col span={16}>
          <Row gutter={12}>
            {[1, 2, 3].map((i) => (
              <Col span={8} key={i}>
                <div style={{ padding: 12, background: "#f7f8fa", borderRadius: 8, textAlign: "center" }}>
                  <Skeleton.Avatar active size={48} shape="circle" />
                  <Skeleton
                    active
                    paragraph={false}
                    title={{ width: "60%" }}
                    style={{ marginTop: 4 }}
                  />
                </div>
              </Col>
            ))}
          </Row>
          <Skeleton active paragraph={{ rows: 3 }} style={{ marginTop: 16 }} />
          <Skeleton active paragraph={{ rows: 2 }} style={{ marginTop: 8 }} />
        </Col>
      </Row>
    </Card>
  );
}
