import { useEffect, useState } from "react";
import { Modal, Tag, Tooltip } from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";
import { useColors, useTokens } from "../styles/ui";

interface ShortcutItem {
  keys: string[];
  description: string;
}

interface ShortcutGroup {
  group: string;
  items: ShortcutItem[];
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    group: "全局导航",
    items: [
      { keys: ["⌘ / Ctrl", "K"], description: "快速打开股票/指标搜索" },
      { keys: ["⌘ / Ctrl", "J"], description: "呼出 / 隐藏 AI 投研 Copilot" },
      { keys: ["⌘ / Ctrl", "B"], description: "展开 / 折叠左侧导航栏" },
      { keys: ["?"], description: "打开键盘快捷键指南" },
      { keys: ["Esc"], description: "关闭当前弹窗 / 退出十字光标" },
    ],
  },
  {
    group: "K 线与图表交互",
    items: [
      { keys: ["←", "→"], description: "左右移动十字光标，查看历史行情" },
      { keys: ["Esc"], description: "退出图表光标聚焦模式" },
    ],
  },
  {
    group: "AI 对话与指令",
    items: [
      { keys: ["/"], description: "呼出技术诊断、横向对比、F10 快捷指令" },
      { keys: ["Enter"], description: "发送当前问题" },
      { keys: ["Shift", "Enter"], description: "输入框换行" },
    ],
  },
];

export default function KeyboardShortcutsModal() {
  const [open, setOpen] = useState(false);
  const colors = useColors();
  const t = useTokens();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement;
      const isInput =
        activeEl instanceof HTMLInputElement ||
        activeEl instanceof HTMLTextAreaElement ||
        (activeEl as HTMLElement)?.isContentEditable;

      if (!isInput && e.key === "?" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <Tooltip title="快捷键指南 (按 ? 呼出)">
        <button
          type="button"
          aria-label="打开键盘快捷键指南"
          className="app-header-shortcuts-button"
          onClick={() => setOpen(true)}
          style={{
            background: "transparent",
            border: "none",
            color: colors?.textSecondary ?? "currentColor",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 32,
            height: 32,
            borderRadius: t?.radius?.sm ?? 4,
            cursor: "pointer",
            fontSize: 16,
            transition: "all 0.2s",
          }}
        >
          <QuestionCircleOutlined />
        </button>
      </Tooltip>

      <Modal
        title="键盘快捷键指南"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={520}
        destroyOnHidden
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "8px 0" }}>
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.group}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: colors.textMuted,
                  marginBottom: 8,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                {group.group}
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  background: colors?.hoverBg ?? "rgba(255,255,255,0.04)",
                  borderRadius: t?.radius?.md ?? 8,
                  padding: "8px 12px",
                  border: `1px solid ${colors?.border ?? "rgba(255,255,255,0.1)"}`,
                }}
              >
                {group.items.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "4px 0",
                    }}
                  >
                    <span style={{ fontSize: 13, color: colors.textPrimary }}>
                      {item.description}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      {item.keys.map((k) => (
                        <Tag
                          key={k}
                          bordered
                          style={{
                            margin: 0,
                            fontFamily: "var(--c-font-mono)",
                            fontSize: 11,
                            fontWeight: 600,
                            padding: "1px 6px",
                            borderRadius: 4,
                            background: colors.cardBg,
                            borderColor: colors.border,
                            color: colors.textPrimary,
                          }}
                        >
                          {k}
                        </Tag>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Modal>
    </>
  );
}
