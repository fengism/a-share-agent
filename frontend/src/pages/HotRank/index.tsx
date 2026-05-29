import { Button, Tag, Typography } from "antd";
import { FireOutlined, HomeOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { HotRankContent } from "../Market/HotRankContent";

const { Title } = Typography;

export default function HotRank() {
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: "100vh", background: "#0b1120", padding: "24px" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 20,
            padding: "20px 24px",
            background: "#111827",
            borderRadius: 12,
            boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <FireOutlined style={{ fontSize: 24, color: "#ef4444" }} />
            <Title level={3} style={{ margin: 0, color: "#e5e7eb" }}>
              热点榜单
            </Title>
            <Tag color="red" style={{ marginLeft: 4 }}>
              同花顺
            </Tag>
          </div>
          <Button icon={<HomeOutlined />} onClick={() => navigate("/")}>
            返回首页
          </Button>
        </div>

        <HotRankContent />
      </div>
    </div>
  );
}
