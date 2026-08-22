export interface BatchAnalysisResult {
  succeeded: string[];
  failed: string[];
}

export async function runBatchAnalysis(
  codes: string[],
  start: (code: string) => Promise<void>,
  onProgress: (completed: number, total: number) => void,
  concurrency = 2,
): Promise<BatchAnalysisResult> {
  const uniqueCodes = Array.from(new Set(codes));
  const succeeded = new Set<string>();
  const failed = new Set<string>();
  let nextIndex = 0;
  let completed = 0;

  const worker = async () => {
    while (nextIndex < uniqueCodes.length) {
      const code = uniqueCodes[nextIndex];
      nextIndex += 1;
      try {
        await start(code);
        succeeded.add(code);
      } catch {
        failed.add(code);
      } finally {
        completed += 1;
        onProgress(completed, uniqueCodes.length);
      }
    }
  };

  const workerCount = Math.min(Math.max(1, concurrency), uniqueCodes.length);
  await Promise.all(Array.from({ length: workerCount }, worker));
  return {
    succeeded: uniqueCodes.filter((code) => succeeded.has(code)),
    failed: uniqueCodes.filter((code) => failed.has(code)),
  };
}
