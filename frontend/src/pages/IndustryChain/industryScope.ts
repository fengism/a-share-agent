import type { IndustryChainResearchScope } from "../../types/stock";

export const DEFAULT_INDUSTRY_SCOPE: IndustryChainResearchScope = {
  region: "china_and_global",
  time_range: "half_year",
  company_scope: "a_share",
};

export function validateIndustryScope(scope: IndustryChainResearchScope): string {
  if (scope.time_range === "custom") {
    if (!scope.start_date || !scope.end_date) return "自定义时间范围需要填写开始日期和结束日期";
    if (scope.start_date > scope.end_date) return "开始日期不能晚于结束日期";
  }
  if (scope.as_of_date && scope.end_date && scope.end_date > scope.as_of_date) {
    return "结束日期不能晚于分析基准日期";
  }
  return "";
}

export function industryScopeRequest(scope: IndustryChainResearchScope): IndustryChainResearchScope {
  return {
    region: scope.region,
    time_range: scope.time_range,
    company_scope: scope.company_scope,
    ...(scope.refresh_dimensions?.length ? { refresh_dimensions: scope.refresh_dimensions } : {}),
    ...(scope.start_date ? { start_date: scope.start_date } : {}),
    ...(scope.end_date ? { end_date: scope.end_date } : {}),
    ...(scope.as_of_date ? { as_of_date: scope.as_of_date } : {}),
  };
}
