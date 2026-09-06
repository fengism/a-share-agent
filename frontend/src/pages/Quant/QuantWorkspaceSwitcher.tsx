import { lazy, Suspense, useEffect } from "react";
import { ExperimentOutlined, RobotOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import type { QuantBacktestRun } from "../../api/queries";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import QuantBacktestWorkspace from "./QuantBacktestWorkspace";
import QuantWorkspaceFallback from "./QuantWorkspaceFallback";
import { loadStrategyAuthoringWorkbench, preloadQuantModule } from "./quantLazyLoaders";
import { selectQuantBacktestFromAuthoring } from "./quantUrlState";
import type { QuantRunController } from "./useQuantRunController";

const WORKSPACE_VIEWS = ["backtest", "authoring"] as const;
type WorkspaceView = (typeof WORKSPACE_VIEWS)[number];
const StrategyAuthoringWorkbench = lazy(loadStrategyAuthoringWorkbench);

export default function QuantWorkspaceSwitcher({
  initialCodes,
  isAdmin,
  runController,
}: {
  initialCodes: string[];
  isAdmin: boolean;
  runController: QuantRunController;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [workspaceView, setWorkspaceView] = useUrlSearchParam<WorkspaceView>("view", "backtest", {
    allowedValues: WORKSPACE_VIEWS,
  });

  useEffect(() => {
    if (isAdmin || !searchParams.has("view")) return;
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("view");
      return next;
    }, { replace: true });
  }, [isAdmin, searchParams, setSearchParams]);

  const backtestWorkspace = (
    <QuantBacktestWorkspace initialCodes={initialCodes} runController={runController} />
  );

  if (!isAdmin) return backtestWorkspace;

  const handleAuthoringCreated = (run: QuantBacktestRun) => {
    setSearchParams((current) => selectQuantBacktestFromAuthoring(current, run.id));
  };

  return (
    <div className="quant-workspace-switcher">
      <ResponsiveSectionNav
        activeKey={workspaceView}
        onChange={(key) => setWorkspaceView(key as WorkspaceView)}
        ariaLabel="量化研究工作区"
        tabBarGutter={16}
        tabBarStyle={{ marginBottom: 20, fontWeight: "var(--c-weight-bold)" }}
        preserveVisited
        items={[
          {
            key: "backtest",
            label: <span><ExperimentOutlined /> 回测实验</span>,
            mobileLabel: "回测实验",
            children: backtestWorkspace,
          },
          {
            key: "authoring",
            label: <span><RobotOutlined /> 在线策略</span>,
            mobileLabel: "在线策略",
            onIntent: () => preloadQuantModule(loadStrategyAuthoringWorkbench),
            children: (
              <Suspense fallback={<QuantWorkspaceFallback label="在线策略工作台加载中" />}>
                <StrategyAuthoringWorkbench onBacktestCreated={handleAuthoringCreated} />
              </Suspense>
            ),
          },
        ]}
      />
    </div>
  );
}
