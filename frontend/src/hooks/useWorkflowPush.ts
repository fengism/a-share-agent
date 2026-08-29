import { createElement, useCallback, useRef } from "react";
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

function feedbackContent(text: string, url: string, linkText: string) {
  if (!url) return text;
  return createElement(
    "span",
    null,
    `${text} `,
    createElement("a", {
      href: url,
      target: "_blank",
      rel: "noreferrer",
    }, linkText),
  );
}

export function useWorkflowPush() {
  const { mutateAsync, isPending } = usePush();
  const isPushingRef = useRef(false);

  const push = useCallback(async (request: PushRequest): Promise<PushResponse | null> => {
    if (isPushingRef.current) return null;
    isPushingRef.current = true;
    try {
      const result = await mutateAsync(request);
      if (!result.success) {
        message.warning({
          content: feedbackContent(
            result.message || "推送未完全完成",
            result.url,
            "打开文档",
          ),
          duration: 8,
        });
        return result;
      }
      const successText = result.target === "notion"
        ? `已转存 Notion：${result.title}`
        : `已推送到飞书：${result.message || result.title}`;
      message.success({
        content: feedbackContent(successText, result.url, "打开"),
        duration: result.url ? 6 : 3,
      });
      return result;
    } catch (error) {
      message.error(`推送失败: ${pushErrorMessage(error)}`);
      return null;
    } finally {
      isPushingRef.current = false;
    }
  }, [mutateAsync]);

  return { push, isPushing: isPending };
}
