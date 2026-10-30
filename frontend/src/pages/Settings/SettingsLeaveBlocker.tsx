import { useUnsavedChangesGuard } from "../../hooks/useUnsavedChangesGuard";

interface SettingsLeaveBlockerProps {
  /** 是否存在未保存的配置变更 */
  hasUnsavedChanges: boolean;
  /** 变更卡片数量，用于提示文案 */
  dirtyCardCount: number;
}

/**
 * 设置页的离开保护。
 *
 * 文案按"卡片"组织（设置页以卡片为单位保存），站内跳转与刷新/关页都由
 * `useUnsavedChangesGuard` 统一处理；该组件只在 Router 上下文内挂载。
 */
export default function SettingsLeaveBlocker({ hasUnsavedChanges, dirtyCardCount }: SettingsLeaveBlockerProps) {
  useUnsavedChangesGuard({
    hasUnsavedChanges,
    title: "有未保存的配置变更",
    description: dirtyCardCount > 0
      ? `当前有 ${dirtyCardCount} 张配置卡片尚未保存，离开后这些修改将丢失。`
      : "当前有尚未保存的配置修改，离开后这些修改将丢失。",
  });

  return null;
}
