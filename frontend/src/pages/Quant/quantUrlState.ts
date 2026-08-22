export function parseQuantStockCodes(params: URLSearchParams): string[] {
  return Array.from(new Set(
    (params.get("codes") ?? "")
      .split(/[，,\s]+/)
      .map((code) => code.trim())
      .filter((code) => /^\d{6}$/.test(code)),
  )).slice(0, 10);
}

export function selectQuantBacktestFromAuthoring(
  current: URLSearchParams,
  runId: string,
): URLSearchParams {
  const next = new URLSearchParams(current);
  next.set("run", runId);
  next.set("panel", "runs");
  next.delete("view");
  return next;
}

export function selectQuantResult(current: URLSearchParams, runId: string): URLSearchParams {
  const next = new URLSearchParams(current);
  next.set("run", runId);
  next.set("panel", "result");
  return next;
}

export function selectQuantTask(current: URLSearchParams, runId: string): URLSearchParams {
  const next = new URLSearchParams(current);
  next.set("run", runId);
  next.set("panel", "runs");
  return next;
}
