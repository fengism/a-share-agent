export const loadResearchFrameworkPanel = () => import("./ResearchFrameworkPanel");
export const loadTechnicalPanel = () => import("./TechnicalPanel");
export const loadValuationPanel = () => import("./ValuationPanel");
export const loadSentimentPanel = () => import("./SentimentPanel");
export const loadFundFlowPanel = () => import("./FundFlowPanel");

export async function preloadAnalysisPanelModules() {
  await Promise.all([
    loadResearchFrameworkPanel(),
    loadTechnicalPanel(),
    loadValuationPanel(),
    loadSentimentPanel(),
    loadFundFlowPanel(),
  ]);
}
