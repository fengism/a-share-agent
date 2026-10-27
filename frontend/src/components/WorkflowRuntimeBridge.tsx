import { useEffect, useRef } from "react";
import { useActiveWorkflows, type WorkflowJob } from "../api/queries";
import {
  resumeAnalysisWorkflow,
  resumeDailyReviewWorkflow,
  resumeIndustryChainWorkflow,
} from "../features/workflows/workflowRuntime";

export default function WorkflowRuntimeBridge() {
  const active = useActiveWorkflows();
  const resumedJobs = useRef(new Set<string>());

  useEffect(() => {
    if (!active.isSuccess) return;
    const jobs = active.data ?? [];
    // 不再限制"仅首次挂载恢复"：轮询中新出现的活动任务（其他端提交、
    // 或本端流结束后任务仍在跑）也会被恢复；每个 resume 函数内部有
    // 同任务守卫，不会重复建流。
    for (const job of jobs) {
      if (resumedJobs.current.has(job.id)) continue;
      resumedJobs.current.add(job.id);
      if (job.kind === "analysis") resumeAnalysisWorkflow(job as WorkflowJob);
      else if (job.kind === "industry_chain") resumeIndustryChainWorkflow(job as WorkflowJob);
      else if (job.kind === "daily_review") resumeDailyReviewWorkflow(job as WorkflowJob);
    }
    const activeIds = new Set(jobs.map((job) => job.id));
    for (const jobId of resumedJobs.current) {
      if (!activeIds.has(jobId)) resumedJobs.current.delete(jobId);
    }
  }, [active.data, active.isSuccess]);

  return null;
}
