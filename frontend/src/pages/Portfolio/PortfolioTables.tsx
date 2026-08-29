import { memo } from "react";
import type {
  PortfolioClosedPosition,
  PortfolioPosition,
  PortfolioStockSummary,
  PortfolioTransaction,
} from "../../types/portfolio";
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
}

function PortfolioTables({
  positions,
  stocks,
  transactions,
  closedPositions,
  onSell,
}: PortfolioTablesProps) {
  const renderers = usePortfolioTableRenderers();

  return (
    <>
      <PortfolioStockTable stocks={stocks} renderers={renderers} onSell={onSell} />
      <PortfolioClosedPositionTable closedPositions={closedPositions} renderers={renderers} />
      <PortfolioLotTable positions={positions} renderers={renderers} />
      <PortfolioTransactionTable transactions={transactions} renderers={renderers} />
    </>
  );
}

export default memo(PortfolioTables);
