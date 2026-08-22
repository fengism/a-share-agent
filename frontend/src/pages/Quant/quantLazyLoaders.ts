export const loadBacktestResult = () => import("./BacktestResult");
export const loadStrategyAuthoringWorkbench = () => import("./StrategyAuthoringWorkbench");

export function preloadQuantModule(loader: () => Promise<unknown>) {
  void loader().catch(() => undefined);
}
