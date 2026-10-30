import { useEffect } from "react";
import { useBlocker } from "react-router-dom";
import { Modal } from "antd";

interface UseUnsavedChangesGuardOptions {
  /** 是否存在未保存的修改 */
  hasUnsavedChanges: boolean;
  /** 确认弹窗标题 */
  title?: string;
  /** 确认弹窗正文 */
  description?: string;
}

/**
 * 未保存修改的离开保护（站内路由 + 刷新/关页）。
 *
 * - 站内跳转：依赖 data router 的 `useBlocker`，弹确认后才放行；
 * - 刷新 / 关闭标签页：注册 `beforeunload`（浏览器原生提示）。
 *
 * 必须在 Router 上下文内调用；非 data router 环境（如仅用 MemoryRouter 的测试）
 * 请由调用方决定是否挂载本 hook。
 */
export function useUnsavedChangesGuard({
  hasUnsavedChanges,
  title = "有未保存的修改",
  description = "离开后这些修改将丢失，确定要离开吗？",
}: UseUnsavedChangesGuardOptions) {
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      hasUnsavedChanges && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    const modal = Modal.confirm({
      title,
      content: description,
      okText: "放弃修改并离开",
      cancelText: "留在本页",
      okButtonProps: { danger: true },
      onOk: () => blocker.proceed(),
      onCancel: () => blocker.reset(),
    });
    return () => modal.destroy();
  }, [blocker, description, title]);

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);
}
