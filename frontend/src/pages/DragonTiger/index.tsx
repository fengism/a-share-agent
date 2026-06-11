import { Button, Tag, Typography } from "antd";
import { HomeOutlined, SwapRightOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { DragonTigerContent } from "../Market/DragonTigerContent";
import { useColors } from "../../styles/ui";

const { Title } = Typography;

export default function DragonTiger() {
  const c = useColors();
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: "100vh", background: c.pageBg, padding: "24px" }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 20,
            padding: "20px 24px",
            background: c.cardBg,
            borderRadius: 12,
            boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <SwapRightOutlined
              style={{ fontSize: 22, color: "#eab308", transform: "rotate(90deg)" }}
            />
            <Title level={3} style={{ margin: 0, color: c.textPrimary }}>
              龙虎榜
            </Title>
            <Tag color="orange" style={{ marginLeft: 4 }}>
              东方财富
            </Tag>
          </div>
          <Button icon={<HomeOutlined />} onClick={() => navigate("/")}>
            返回首页
          </Button>
        </div>

        <DragonTigerContent />
      </div>
    </div>
  );
}
