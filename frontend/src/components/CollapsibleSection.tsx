import { useId, useState, type ReactNode } from "react";
import { DownOutlined } from "@ant-design/icons";
import "./collapsible-section.css";

interface CollapsibleSectionProps {
  id: string;
  title: string;
  /** 标题右侧摘要，如「3 条」「命中 3/4」 */
  summary?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  /** 受控展开状态（与 URL 同步时使用） */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/**
 * 可折叠内容分区。
 *
 * 复盘这类长页面单屏塞十几段内容时，默认折叠 + 标题摘要能让用户先扫一遍
 * 全貌再决定展开哪段，避免"无限下拉"。
 */
export default function CollapsibleSection({
  id,
  title,
  summary,
  children,
  defaultOpen = false,
  open,
  onOpenChange,
}: CollapsibleSectionProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const isControlled = open !== undefined;
  const expanded = isControlled ? open : internalOpen;
  const contentId = useId();

  const toggle = () => {
    const next = !expanded;
    if (!isControlled) setInternalOpen(next);
    onOpenChange?.(next);
  };

  return (
    <section id={id} className="collapsible-section" data-open={expanded ? "true" : "false"}>
      <h3 className="collapsible-section__heading">
        <button
          type="button"
          className="collapsible-section__trigger"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={toggle}
        >
          <span className="collapsible-section__title">{title}</span>
          {summary ? <span className="collapsible-section__summary">{summary}</span> : null}
          <DownOutlined className="collapsible-section__chevron" />
        </button>
      </h3>
      <div id={contentId} className="collapsible-section__content" hidden={!expanded}>
        {children}
      </div>
    </section>
  );
}
