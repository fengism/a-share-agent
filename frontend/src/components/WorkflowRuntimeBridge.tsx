import { useEffect, useRef } from "react";
import { useActiveWorkflows, type WorkflowJob } from "../api/queries";
import {
  resumeAnalysisWorkflow,
  resumeIndustryChainWorkflow,
} from "../features/workflows/workflowRuntime";

export default function WorkflowRuntimeBridge() {
  const active = useActiveWorkflows();
  const resumedJobs = useRef(new Set<string>());
  const initialized = useRef(false);

  useEffect(() => {
    if (!active.isSuccess) return;
    const jobs = active.data ?? [];
    if (!initialized.current) {
      for (const job of jobs) {
        if (job.kind === "analysis") resumeAnalysisWorkflow(job as WorkflowJob);
        if (job.kind === "industry_chain") resumeIndustryChainWorkflow(job as WorkflowJob);
        resumedJobs.current.add(job.id);
      }
      initialized.current = true;
    }
    const activeIds = new Set(jobs.map((job) => job.id));
    for (const jobId of resumedJobs.current) {
      if (!activeIds.has(jobId)) resumedJobs.current.delete(jobId);
    }
  }, [active.data, active.isSuccess]);

  return null;
}
