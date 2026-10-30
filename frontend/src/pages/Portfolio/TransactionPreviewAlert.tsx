import { Alert, Space, Typography } from "antd";
import type { PortfolioTransactionPreview } from "../../types/portfolio";
import { isHkStockCode } from "../../utils/stockLinks";
import { formatInteger, formatMoney, formatPrice, formatTime } from "./portfolioFormatters";

const { Text } = Typography;

interface TransactionPreviewAlertProps {
  preview: PortfolioTransactionPreview;
  title: string;
}

function formatPct(value: number | null | undefined) {
  return value == null ? "-" : `${value.toFixed(2)}%`;
}

export default function TransactionPreviewAlert({ preview, title }: TransactionPreviewAlertProps) {
  const isSell = preview.side === "sell";
  const hasWarnings = Boolean(preview.warnings?.length);
  const isTPlusOneBuy = !isSell && !isHkStockCode(preview.stock_code);

  return (
    <Alert
      type={hasWarnings || (isSell && preview.realized_profit_amount != null && preview.realized_profit_amount < 0)
        ? "warning"
        : "success"}
      showIcon
      title={title}
      description={(
        <Space orientation="vertical" size={6} style={{ width: "100%" }}>
          <span>
            {isSell ? "卖出" : "买入"}金额 {formatMoney(preview.trade_amount)}（人民币），
            手续费 {formatMoney(preview.fee)}。
          </span>
          {preview.currency !== "CNY" ? (
            <span>
              原币成交额 {formatMoney(preview.trade_amount_native, preview.currency)}，
              原币手续费 {formatMoney(preview.fee_native, preview.currency)}，
              折算汇率 1 {preview.currency} = {preview.fx_rate_to_cny} CNY。
            </span>
          ) : null}
          <span>
            交易后现金 {formatMoney(preview.cash_balance_after)}，
            预计总资产 {formatMoney(preview.estimated_total_assets_after)}，
            总仓位 {formatPct(preview.total_position_pct_after)}。
          </span>
          <span>
            单股仓位 {formatPct(preview.stock_position_pct_after)}
            {preview.sector_name
              ? `，${preview.sector_name}行业仓位 ${formatPct(preview.sector_position_pct_after)}。`
              : "，暂未获取行业归属。"}
          </span>
          {preview.sellable_shares != null ? (
            <span>
              当前可卖 {formatInteger(preview.sellable_shares)} 股，
              冻结 {formatInteger(preview.frozen_shares ?? 0)} 股
              {preview.sellable_after_trade != null
                ? `，交易后预计可卖 ${formatInteger(preview.sellable_after_trade)} 股。`
                : "。"}
            </span>
          ) : null}
          {isTPlusOneBuy ? (
            <span>A 股 T+1：本次买入的股份当日不可卖出，次一交易日可卖。</span>
          ) : null}
          {isSell ? (
            <>
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
                  {formatPrice(match.buy_price, preview.currency)} × {formatInteger(match.shares)} 股，
                  成本 {formatMoney(match.matched_cost)}）
                </span>
              ))}
            </>
          ) : (
            <span>
              买入后该股票持有 {formatInteger(preview.shares_after_trade)} 股，
              按当前全部流水回放后持有 {formatInteger(preview.current_shares_after)} 股。
            </span>
          )}
          {(preview.warnings ?? []).map((warning) => (
            <Text key={warning} strong type="warning">风险提示：{warning}</Text>
          ))}
        </Space>
      )}
    />
  );
}
