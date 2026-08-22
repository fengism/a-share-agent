import { Alert, Space, Tag, Typography } from "antd";
import { semanticTagStyle } from "../../styles/ui";

const { Text } = Typography;

interface PortfolioQuoteStatusProps {
  quotedAt: string;
  source: string;
  stale: boolean;
}

export default function PortfolioQuoteStatus({ quotedAt, source, stale }: PortfolioQuoteStatusProps) {
  return (
    <div>
      <Space size={[6, 6]} wrap>
        <Tag style={semanticTagStyle(stale ? "warning" : "info")}>{stale ? "缓存行情" : "最新行情"}</Tag>
        <Text type="secondary" style={{ fontSize: 12 }}>来源：{source || "未标注"}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>行情时间：{quotedAt}</Text>
      </Space>
      {stale ? (
        <Alert
          type="warning"
          showIcon
          title="实时行情获取失败，当前使用最近一次缓存，行情可能已经过期。"
          style={{ marginTop: 8 }}
        />
      ) : null}
    </div>
  );
}
