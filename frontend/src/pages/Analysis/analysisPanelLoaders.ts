export const loadTechnicalPanel = () => import("./TechnicalPanel");
export const loadValuationPanel = () => import("./ValuationPanel");
export const loadSentimentPanel = () => import("./SentimentPanel");
export const loadFundFlowPanel = () => import("./FundFlowPanel");

export async function preloadAnalysisPanelModules() {
  await Promise.all([
    loadTechnicalPanel(),
    loadValuationPanel(),
    loadSentimentPanel(),
    loadFundFlowPanel(),
  ]);
}
