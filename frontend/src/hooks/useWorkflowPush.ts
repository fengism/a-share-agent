import { useCallback, useRef } from "react";
import { message } from "antd";
import { usePush } from "../api/queries";
import type { PushRequest, PushResponse } from "../types/stock";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function pushErrorMessage(error: unknown) {
  if (isRecord(error)) {
    const response = isRecord(error.response) ? error.response : null;
    const data = response && isRecord(response.data) ? response.data : null;
    if (data && typeof data.detail === "string" && data.detail) return data.detail;
  }
  if (error instanceof Error && error.message) return error.message;
  if (isRecord(error) && typeof error.message === "string" && error.message) return error.message;
  return "未知错误";
}

export function useWorkflowPush() {
  const mutation = usePush();
  const isPushingRef = useRef(false);

  const push = useCallback(async (request: PushRequest): Promise<PushResponse | null> => {
    if (isPushingRef.current) return null;
    isPushingRef.current = true;
    try {
      const result = await mutation.mutateAsync(request);
      if (result.target === "notion") {
        message.success(`已转存 Notion：${result.title}`);
      } else {
        message.success(`已推送到飞书：${result.message || result.title}`);
      }
      return result;
    } catch (error) {
      message.error(`推送失败: ${pushErrorMessage(error)}`);
      return null;
    } finally {
      isPushingRef.current = false;
    }
  }, [mutation]);

  return { push, isPushing: mutation.isPending };
}
