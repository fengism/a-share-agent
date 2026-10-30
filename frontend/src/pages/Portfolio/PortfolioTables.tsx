import { memo, useMemo, useState } from "react";
import { Card, Tabs } from "antd";
import type {
  PortfolioClosedPosition,
  PortfolioPosition,
  PortfolioStockSummary,
  PortfolioTransaction,
} from "../../types/portfolio";
import { useStyles } from "../../styles/ui";
import PortfolioClosedPositionTable from "./PortfolioClosedPositionTable";
import PortfolioLotTable from "./PortfolioLotTable";
import PortfolioStockTable from "./PortfolioStockTable";
import PortfolioTransactionTable from "./PortfolioTransactionTable";
import { usePortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioTablesProps {
  positions: PortfolioPosition[];
  stocks: PortfolioStockSummary[];
  transactions: PortfolioTransaction[];
  closedPositions: PortfolioClosedPosition[];
  onSell: (stock: PortfolioStockSummary) => void;
  onViewKline?: (stockCode: string) => void;
}

function PortfolioTables({
  positions,
  stocks,
  transactions,
  closedPositions,
  onSell,
  onViewKline,
}: PortfolioTablesProps) {
  const { cardStyle } = useStyles();
  const renderers = usePortfolioTableRenderers();

  const initialKey = useMemo(() => {
    if (stocks.length > 0) return "stocks";
    if (closedPositions.length > 0) return "closed";
    if (transactions.length > 0) return "transactions";
    if (positions.length > 0) return "lots";
    return "stocks";
  }, [stocks.length, closedPositions.length, transactions.length, positions.length]);

  const [activeKey, setActiveKey] = useState(initialKey);

  const tabItems = useMemo(() => [
    {
      key: "stocks",
      label: (
        <span>
          <span>当前持仓</span>
          {stocks.length > 0 ? (
            <span className="portfolio-tab-badge"> ({stocks.length})</span>
          ) : null}
        </span>
      ),
      children: (
        <PortfolioStockTable
          stocks={stocks}
          renderers={renderers}
          onSell={onSell}
          onViewKline={onViewKline}
          bare
        />
      ),
      forceRender: true,
    },
    {
      key: "lots",
      label: (
        <span>
          <span>FIFO 剩余批次</span>
          {positions.length > 0 ? (
            <span className="portfolio-tab-badge"> ({positions.length})</span>
          ) : null}
        </span>
      ),
      children: <PortfolioLotTable positions={positions} renderers={renderers} bare />,
      forceRender: true,
    },
    {
      key: "closed",
      label: (
        <span>
          <span>已清仓股票</span>
          {closedPositions.length > 0 ? (
            <span className="portfolio-tab-badge"> ({closedPositions.length})</span>
          ) : null}
        </span>
      ),
      children: <PortfolioClosedPositionTable closedPositions={closedPositions} renderers={renderers} bare />,
      forceRender: true,
    },
    {
      key: "transactions",
      label: (
        <span>
          <span>交易流水</span>
          {transactions.length > 0 ? (
            <span className="portfolio-tab-badge"> ({transactions.length})</span>
          ) : null}
        </span>
      ),
      children: <PortfolioTransactionTable transactions={transactions} renderers={renderers} bare />,
      forceRender: true,
    },
  ], [closedPositions, onSell, onViewKline, positions, renderers, stocks, transactions]);

  return (
    <Card
      size="small"
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: { padding: "8px 12px 12px" } }}
      className="portfolio-tables-card"
    >
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        items={tabItems}
        size="small"
        className="portfolio-tables-tabs"
      />
    </Card>
  );
}

export default memo(PortfolioTables);
