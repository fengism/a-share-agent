import {
  BellOutlined,
  ExperimentOutlined,
  FilterOutlined,
  StarOutlined,
} from "@ant-design/icons";
import { Button, Space, Tag, Typography } from "antd";
import { useTokens } from "../../../styles/ui";
import type {
  ChatResultActionHandler,
  ChatResultContext,
} from "../chatResultActions";

const { Text } = Typography;

interface ChatResultActionsProps {
  context: ChatResultContext;
  onAction: ChatResultActionHandler;
}

export function ChatResultActions({ context, onAction }: ChatResultActionsProps) {
  const t = useTokens();
  const hasStocks = context.stockCodes.length > 0;
  if (!hasStocks && !context.screenerState) return null;

  return (
    <div className="chat-result-actions">
      <Space size={6} wrap>
        <Text type="secondary" style={{ fontSize: t.font.sm }}>可继续操作</Text>
        {hasStocks ? <Tag>{context.stockCodes.length} 只股票</Tag> : null}
        {hasStocks ? (
          <Button size="small" icon={<StarOutlined />} onClick={() => onAction("watchlist", context)}>
            加入自选
          </Button>
        ) : null}
        {hasStocks ? (
          <Button size="small" icon={<BellOutlined />} onClick={() => onAction("alert", context)}>
            设置提醒
          </Button>
        ) : null}
        {context.screenerState ? (
          <Button size="small" icon={<FilterOutlined />} onClick={() => onAction("screener", context)}>
            保存筛选方案
          </Button>
        ) : null}
        {hasStocks ? (
          <Button size="small" icon={<ExperimentOutlined />} onClick={() => onAction("quant", context)}>
            转为量化策略
          </Button>
        ) : null}
      </Space>
    </div>
  );
}
