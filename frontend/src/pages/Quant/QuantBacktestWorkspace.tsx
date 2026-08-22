import { ExperimentOutlined, HistoryOutlined, LineChartOutlined } from "@ant-design/icons";
import { Badge } from "antd";
import { useSearchParams } from "react-router-dom";
import type { QuantBacktestRun } from "../../api/queries";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import BacktestForm from "./BacktestForm";
import BacktestResultSection from "./BacktestResultSection";
import BacktestTaskWorkspace from "./BacktestTaskWorkspace";
import { loadBacktestResult, preloadQuantModule } from "./quantLazyLoaders";
import { selectQuantResult, selectQuantTask } from "./quantUrlState";
import type { QuantRunController } from "./useQuantRunController";

const BACKTEST_PANELS = ["setup", "runs", "result"] as const;
type BacktestPanel = (typeof BACKTEST_PANELS)[number];

export default function QuantBacktestWorkspace({
  initialCodes,
  runController,
}: {
  initialCodes: string[];
  runController: QuantRunController;
}) {
  const [, setSearchParams] = useSearchParams();
  const [activePanel, setActivePanel] = useUrlSearchParam<BacktestPanel>("panel", "setup", {
    allowedValues: BACKTEST_PANELS,
  });
  const activeRunCount = runController.runs.filter((run) => (
    run.status === "pending" || run.status === "running"
  )).length;
  const resultReady = runController.selectedRun?.status === "succeeded"
    && Boolean(runController.selectedRun.result);

  const handleCreated = (run: QuantBacktestRun) => {
    setSearchParams((current) => selectQuantTask(current, run.id));
  };

  return (
    <section className="quant-backtest-workspace" aria-label="量化回测工作台">
      <ResponsiveSectionNav
        activeKey={activePanel}
        onChange={(key) => setActivePanel(key as BacktestPanel)}
        ariaLabel="量化回测视图"
        size="middle"
        tabBarGutter={12}
        tabBarStyle={{ marginBottom: 20, fontWeight: 700 }}
        preserveVisited
        items={[
          {
            key: "setup",
            label: <span><ExperimentOutlined /> 配置回测</span>,
            mobileLabel: "配置回测",
            children: (
              <section className="quant-config-panel" aria-label="量化回测配置">
                <BacktestForm initialCodes={initialCodes} onCreated={handleCreated} />
              </section>
            ),
          },
          {
            key: "runs",
            preserve: false,
            label: (
              <span className="quant-tab-label">
                <HistoryOutlined /> 任务记录
                {activeRunCount > 0 ? <Badge count={activeRunCount} size="small" /> : null}
              </span>
            ),
            mobileLabel: "任务记录",
            children: (
              <BacktestTaskWorkspace
                controller={runController}
                onOpenSetup={() => setActivePanel("setup")}
                onOpenResult={(runId) => {
                  setSearchParams((current) => selectQuantResult(current, runId));
                }}
              />
            ),
          },
          {
            key: "result",
            preserve: false,
            label: (
              <span className="quant-tab-label">
                <LineChartOutlined /> 结果分析
                {resultReady ? <span className="quant-nav-state">可查看</span> : null}
              </span>
            ),
            mobileLabel: "结果分析",
            onIntent: () => preloadQuantModule(loadBacktestResult),
            children: (
              <BacktestResultSection
                run={runController.selectedRun}
                onBackToRuns={() => setActivePanel("runs")}
              />
            ),
          },
        ]}
      />
    </section>
  );
}
