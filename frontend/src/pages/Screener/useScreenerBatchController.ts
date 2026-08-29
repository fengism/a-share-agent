import { useCallback, useState } from "react";
import { message } from "antd";
import { useAddWatchlistItem } from "../../api/queries";
import { streamAnalysis } from "../../api/sse";
import { runBatchAnalysis } from "./batchAnalysis";

export function useScreenerBatchController() {
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [isAddingWatchlist, setIsAddingWatchlist] = useState(false);
  const [isBatchAnalyzing, setIsBatchAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState("");
  const addWatchlistItem = useAddWatchlistItem();

  const handleAddSelectedToWatchlist = useCallback(async () => {
    setIsAddingWatchlist(true);
    let succeeded = 0;
    try {
      for (const stockCode of selectedCodes) {
        try {
          await addWatchlistItem.mutateAsync({ stock_code: stockCode, note: "" });
          succeeded += 1;
        } catch {
          continue;
        }
      }
      const failed = selectedCodes.length - succeeded;
      if (failed === 0) message.success(`已将 ${succeeded} 只股票加入自选`);
      else message.warning(`已加入 ${succeeded} 只，${failed} 只添加失败`);
    } finally {
      setIsAddingWatchlist(false);
    }
  }, [addWatchlistItem, selectedCodes]);

  const handleBatchAnalyze = useCallback(async () => {
    setIsBatchAnalyzing(true);
    setAnalysisProgress(`分析中 0/${selectedCodes.length}`);
    try {
      const result = await runBatchAnalysis(
        selectedCodes,
        async (stockCode) => {
          await streamAnalysis(stockCode, () => undefined).promise;
        },
        (completed, total) => setAnalysisProgress(`分析中 ${completed}/${total}`),
      );
      if (result.failed.length === 0) {
        message.success(`已完成 ${result.succeeded.length} 只股票研究，可在研究历史中查看`);
      } else {
        message.warning(`完成 ${result.succeeded.length} 只，失败 ${result.failed.length} 只`);
      }
    } finally {
      setIsBatchAnalyzing(false);
      setAnalysisProgress("");
    }
  }, [selectedCodes]);

  return {
    analysisProgress,
    clearSelection: () => setSelectedCodes([]),
    handleAddSelectedToWatchlist,
    handleBatchAnalyze,
    isAddingWatchlist,
    isBatchAnalyzing,
    selectedCodes,
    setSelectedCodes,
  };
}
