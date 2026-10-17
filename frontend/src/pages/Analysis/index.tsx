/**
 * 个股分析页（`/analysis/:code`）。
 *
 * 一个路由承载两个视图：
 * - 默认：个股研究工作台（`AnalysisWorkspaceView`）
 * - `?view=report`：投资研究报告专注阅读（`AnalysisReportView`）
 *
 * 两者共用 `useAnalysisReportPage` 提供的数据、工作流与 PDF 导出管线。
 * 旧路径 `/investment-research/:code` 由路由层重定向到 `?view=report`。
 */

import { message } from "antd";
import { useParams, useSearchParams } from "react-router-dom";
import AnalysisReportView from "./AnalysisReportView";
import AnalysisWorkspaceView from "./AnalysisWorkspaceView";
import { useAnalysisReportPage, type AnalysisViewMode } from "./useAnalysisReportPage";

export default function Analysis() {
  const { code = "" } = useParams<{ code: string }>();
  const [searchParams] = useSearchParams();
  const [messageApi, contextHolder] = message.useMessage();
  const view: AnalysisViewMode = searchParams.get("view") === "report" ? "report" : "workspace";
  const page = useAnalysisReportPage({ code, view, messageApi });

  return (
    <>
      {contextHolder}
      {view === "report" ? (
        <AnalysisReportView page={page} />
      ) : (
        <AnalysisWorkspaceView page={page} messageApi={messageApi} />
      )}
    </>
  );
}
