import type { FundamentalExportData } from "../../types/stock";
import KeyFinancialMetricsSection from "./KeyFinancialMetricsSection";
import RevenueBreakdownSection from "./RevenueBreakdownSection";
import "./financial-data-sections.css";

export default function FinancialDataSections({
  code,
  isExportingPdf = false,
  exportData,
}: {
  code: string;
  isExportingPdf?: boolean;
  exportData?: FundamentalExportData;
}) {
  return (
    <div className="financial-data-sections">
      <RevenueBreakdownSection
        code={code}
        exportData={exportData?.revenueBreakdown}
        isExportingPdf={isExportingPdf}
      />
      <KeyFinancialMetricsSection
        code={code}
        exportData={exportData}
        isExportingPdf={isExportingPdf}
      />
    </div>
  );
}
