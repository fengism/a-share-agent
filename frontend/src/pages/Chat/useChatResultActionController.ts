import { useCallback, useState } from "react";
import { message } from "antd";
import { useNavigate } from "react-router-dom";
import { useAddWatchlistAlert, useAddWatchlistItem, usePush } from "../../api/queries";
import { saveFilter } from "../../features/screener/savedFilters";
import { serializeScreenerUrlState } from "../../features/screener/screenerUrlState";
import { useAuthStore } from "../../store/authStore";
import type { PushRequest } from "../../types/stock";
import type { WatchlistAlertCondition } from "../../types/watchlist";
import type { ChatResultActionHandler } from "./chatResultActions";
import { formatMarketDateTime } from "../../utils/marketTime";

export function useChatResultActionController() {
  const navigate = useNavigate();
  const userId = useAuthStore((state) => state.user?.id);
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const [pushContent, setPushContent] = useState("");
  const [alertCodes, setAlertCodes] = useState<string[]>([]);
  const [alertStockCode, setAlertStockCode] = useState("");
  const [alertCondition, setAlertCondition] = useState<WatchlistAlertCondition>("price_above");
  const [alertThreshold, setAlertThreshold] = useState<number | null>(null);
  const pushMutation = usePush();
  const addWatchlistItem = useAddWatchlistItem();
  const addWatchlistAlert = useAddWatchlistAlert();

  const handleOpenPush = useCallback((_messageId: string, content: string) => {
    setPushContent(content);
    setPushModalOpen(true);
  }, []);

  const handlePushConfirm = async (request: PushRequest) => {
    try {
      const result = await pushMutation.mutateAsync({
        ...request,
        type: "chat",
        chat_content: pushContent,
      });
      if (!result.success) {
        message.error("推送失败");
        return false;
      }
      message.success(`推送成功${result.url ? `：${result.url}` : ""}`);
      setPushModalOpen(false);
      return true;
    } catch {
      message.error("推送失败");
      return false;
    }
  };

  const addStocksToWatchlist = useCallback(async (stockCodes: string[]) => {
    let succeeded = 0;
    for (const stockCode of stockCodes) {
      try {
        await addWatchlistItem.mutateAsync({ stock_code: stockCode, note: "" });
        succeeded += 1;
      } catch {
        continue;
      }
    }
    const failed = stockCodes.length - succeeded;
    if (failed === 0) message.success(`已将 ${succeeded} 只股票加入自选`);
    else message.warning(`已加入 ${succeeded} 只，${failed} 只添加失败`);
  }, [addWatchlistItem]);

  const handleResultAction = useCallback<ChatResultActionHandler>((action, context) => {
    if (action === "watchlist") {
      void addStocksToWatchlist(context.stockCodes);
      return;
    }
    if (action === "alert") {
      setAlertCodes(context.stockCodes);
      setAlertStockCode(context.stockCodes[0] ?? "");
      setAlertThreshold(null);
      return;
    }
    if (action === "screener" && context.screenerState && userId != null) {
      const label = `AI 筛选 ${formatMarketDateTime(Date.now())}`;
      saveFilter(window.localStorage, userId, label, context.screenerState);
      message.success("对话筛选条件已保存");
      navigate(`/screener?${serializeScreenerUrlState(context.screenerState).toString()}`);
      return;
    }
    if (action === "quant") {
      navigate(`/quant?codes=${encodeURIComponent(context.stockCodes.join(","))}`);
    }
  }, [addStocksToWatchlist, navigate, userId]);

  const handleCreateResultAlert = async () => {
    if (!alertStockCode || alertThreshold == null) return;
    try {
      await addWatchlistItem.mutateAsync({ stock_code: alertStockCode, note: "" });
      await addWatchlistAlert.mutateAsync({
        stockCode: alertStockCode,
        request: { condition: alertCondition, threshold: alertThreshold },
      });
      setAlertCodes([]);
      setAlertThreshold(null);
      message.success("提醒规则已创建");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "提醒创建失败");
    }
  };

  return {
    alertCodes,
    alertCondition,
    alertStockCode,
    alertThreshold,
    closeAlert: () => setAlertCodes([]),
    closePush: () => setPushModalOpen(false),
    handleCreateResultAlert,
    handleOpenPush,
    handlePushConfirm,
    handleResultAction,
    isAlertSaving: addWatchlistItem.isPending || addWatchlistAlert.isPending,
    isPushPending: pushMutation.isPending,
    pushModalOpen,
    setAlertCondition,
    setAlertStockCode,
    setAlertThreshold,
  };
}

export type ChatResultActionController = ReturnType<typeof useChatResultActionController>;
