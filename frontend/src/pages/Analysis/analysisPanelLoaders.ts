export const loadResearchFrameworkPanel = () => import("../../features/investment-research/ResearchFrameworkPanel");
export const loadValuationPanel = () => import("../../features/investment-research/ValuationPanel");

export async function preloadAnalysisPanelModules() {
  await Promise.all([
    loadResearchFrameworkPanel(),
    loadValuationPanel(),
  ]);
}
