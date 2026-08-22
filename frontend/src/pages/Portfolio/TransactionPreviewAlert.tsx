import { Alert, Space } from "antd";
import type { PortfolioTransactionPreview } from "../../types/portfolio";
import { formatInteger, formatMoney, formatPrice, formatTime } from "./portfolioFormatters";

interface TransactionPreviewAlertProps {
  preview: PortfolioTransactionPreview;
  title: string;
}

export default function TransactionPreviewAlert({ preview, title }: TransactionPreviewAlertProps) {
  return (
    <Alert
      type={preview.realized_profit_amount != null && preview.realized_profit_amount < 0 ? "warning" : "success"}
      showIcon
      title={title}
      description={(
        <Space orientation="vertical" size={6} style={{ width: "100%" }}>
          <span>
            交易时点可用 {formatInteger(preview.available_shares)} 股，
            卖出后剩余 {formatInteger(preview.shares_after_trade)} 股，
            按当前全部流水回放后剩余 {formatInteger(preview.current_shares_after)} 股。
          </span>
          <span>
            FIFO 匹配成本 {formatMoney(preview.matched_cost)}，
            预计已实现盈亏 {formatMoney(preview.realized_profit_amount)}。
          </span>
          {(preview.matches ?? []).map((match) => (
            <span key={`${match.buy_transaction_id}-${match.buy_time}`}>
              匹配买入 #{match.buy_transaction_id}（{formatTime(match.buy_time)}，
              {formatPrice(match.buy_price)} × {formatInteger(match.shares)} 股，
              成本 {formatMoney(match.matched_cost)}）
            </span>
          ))}
        </Space>
      )}
    />
  );
}
