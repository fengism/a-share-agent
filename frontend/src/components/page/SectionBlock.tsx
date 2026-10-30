import type { ReactNode } from "react";
import "./section-block.css";

interface SectionBlockProps {
  title?: ReactNode;
  /** 标题右侧摘要，如「3 条」「命中 3/4」 */
  extra?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  /** 首个区块不画上分隔线 */
  first?: boolean;
  className?: string;
  id?: string;
}

/**
 * 卡片内的小节块。
 *
 * 以前卡片里再套一层 `Card`，两层边框 + 两层圆角叠在一起，视觉噪音很大；
 * 这里用小节标题 + 分隔线表达层级，只保留外层卡片的一层轮廓。
 */
export default function SectionBlock({
  title,
  extra,
  description,
  children,
  first = false,
  className,
  id,
}: SectionBlockProps) {
  return (
    <section
      id={id}
      className={["section-block", first ? "section-block--first" : "", className].filter(Boolean).join(" ")}
    >
      {(title || extra) && (
        <div className="section-block__head">
          {title ? <h4 className="section-block__title">{title}</h4> : null}
          {extra ? <div className="section-block__extra">{extra}</div> : null}
        </div>
      )}
      {description ? <p className="section-block__description">{description}</p> : null}
      <div className="section-block__body">{children}</div>
    </section>
  );
}
