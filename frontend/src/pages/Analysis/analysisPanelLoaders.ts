export const loadResearchFrameworkPanel = () => import("./ResearchFrameworkPanel");
export const loadValuationPanel = () => import("../../features/investment-research/ValuationPanel");

export async function preloadAnalysisPanelModules() {
  await Promise.all([
    loadResearchFrameworkPanel(),
    loadValuationPanel(),
  ]);
}
