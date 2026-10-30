import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { buildStockAnalysisUrl } from "../utils/stockLinks";

/**
 * 旧路径 `/investment-research/:code` 重定向到 `/analysis/:code?view=report`
 * （保留历史日期参数）。
 */
export default function LegacyResearchRedirect() {
  const { code = "" } = useParams<{ code: string }>();
  const [searchParams] = useSearchParams();
  const params = new URLSearchParams({ view: "report" });
  const date = searchParams.get("date");
  if (date) params.set("date", date);
  return <Navigate to={`${buildStockAnalysisUrl(code)}?${params.toString()}`} replace />;
}
