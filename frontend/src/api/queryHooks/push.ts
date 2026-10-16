import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "../client";

export interface NotificationChannelStatus {
  feishu_configured: boolean;
  dingtalk_configured: boolean;
  wecom_configured: boolean;
  wxpusher_configured: boolean;
  feishu_enabled: boolean;
  dingtalk_enabled: boolean;
  wecom_enabled: boolean;
  wxpusher_enabled: boolean;
  auto_enabled: boolean;
  daily_review_auto: boolean;
  potential_auto: boolean;
}

export interface TestWebhookRequest {
  channel: "feishu" | "wecom" | "wxpusher" | "dingtalk";
  webhook_url?: string;
  secret?: string;
  uids?: string;
}

export interface TestWebhookResponse {
  success: boolean;
  channel: string;
  message: string;
}

export interface NotificationChannelDetail {
  name: string;
  success: boolean;
  message: string;
  elapsed_ms: number;
}

export interface NotificationHistoryItem {
  id: string;
  timestamp: string;
  category: string;
  title: string;
  summary: string;
  severity: string;
  channels: Record<string, NotificationChannelDetail>;
  metadata: Record<string, unknown>;
}

export function useNotificationChannelStatus() {
  return useQuery({
    queryKey: ["push", "channels"],
    queryFn: () => apiGet<NotificationChannelStatus>("/api/push/channels"),
  });
}

export function useTestWebhookNotification() {
  return useMutation({
    mutationFn: (request: TestWebhookRequest) =>
      apiPost<TestWebhookResponse>("/api/push/test-webhook", request),
  });
}

export function useNotificationHistory(limit = 20) {
  return useQuery({
    queryKey: ["push", "history", limit],
    queryFn: () => apiGet<NotificationHistoryItem[]>("/api/push/history", { limit }),
  });
}

export function useClearNotificationHistory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiDelete<{ success: boolean }>("/api/push/history"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["push", "history"] });
    },
  });
}
