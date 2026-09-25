import type { AnalysisResult, FundamentalExportData } from "../../types/stock";
import FinancialDataSections from "../../features/investment-research/FinancialDataSections";
import FundamentalSummary from "../../features/investment-research/FundamentalSummary";
import RevenueBreakdownSection from "../../features/investment-research/RevenueBreakdownSection";

export default function FundamentalPanel({
  code,
  analysis,
  isExportingPdf = false,
  exportData,
}: {
  code: string;
  analysis?: AnalysisResult | null;
  isExportingPdf?: boolean;
  exportData?: FundamentalExportData;
}) {
  return (
    <div style={{ display: "grid", gap: 16, width: "100%", minWidth: 0, overflowX: "hidden" }}>
      <FundamentalSummary fundamental={analysis?.fundamental} />
      {isExportingPdf ? (
        <FinancialDataSections code={code} isExportingPdf exportData={exportData} />
      ) : (
        <RevenueBreakdownSection code={code} />
      )}
    </div>
  );
}
