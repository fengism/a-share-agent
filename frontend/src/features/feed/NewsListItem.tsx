import type { CSSProperties } from "react";
import { LinkOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import dayjs from "dayjs";
import { useColors } from "../../styles/ui";
import type { FeedNewsItem } from "../../types/stock";
import { parseMarketTime } from "../../utils/marketTime";
import {
  formatTime,
  getSourceColor,
  getSourceLabel,
  getTimeColor,
  isTwitterItem,
} from "./feedHelpers";

export type FeedItemLayout = "editorial" | "stream";

export interface NewsListItemProps {
  item: FeedNewsItem;
  showSourceTag?: boolean;
  layout: FeedItemLayout;
  featured?: boolean;
}

function TimeDisplay({ time }: { time: string }) {
  const colors = useColors();
  if (!time) return null;
  const date = dayjs(time);
  if (!date.isValid()) return <span style={{ color: colors.textMuted }}>{time}</span>;

  return (
    <Tooltip title={date.format("YYYY-MM-DD HH:mm:ss")}>
      <span style={{ color: getTimeColor(time, colors) }}>{formatTime(time)}</span>
    </Tooltip>
  );
}

function MediaPreview({ imageUrl, title }: { imageUrl: string; title: string }) {
  if (!imageUrl) return null;
  return (
    <div className="feed-media-preview">
      <img src={imageUrl} alt={title} loading="lazy" />
    </div>
  );
}

export default function NewsListItem({
  item,
  showSourceTag = true,
  layout,
  featured = false,
}: NewsListItemProps) {
  const colors = useColors();
  const sourceColor = getSourceColor(item.source, colors);
  const sourceLabel = getSourceLabel(item.source, colors);
  const parsedTime = item.publish_time ? parseMarketTime(item.publish_time) : null;
  const isFresh = Boolean(parsedTime && dayjs().diff(dayjs(parsedTime), "minute") < 30);

  const itemClassName = [
    "feed-news-item",
    featured ? "is-featured" : "",
    isTwitterItem(item) ? "is-social" : "",
    isFresh ? "is-fresh" : "",
  ].filter(Boolean).join(" ");
  const sourceStyle = { "--feed-source-color": sourceColor } as CSSProperties;
  const titleContent = (
    <>
      {item.title}
      {item.url ? <LinkOutlined style={{ marginLeft: 6, fontSize: 10, color: colors.textMuted }} /> : null}
    </>
  );

  return (
    <article className={itemClassName} data-layout={layout}>
      {layout === "stream" && (
        <div className="feed-stream-indicator" aria-hidden="true">
          <span className="feed-stream-dot" />
          <span className="feed-stream-line" />
        </div>
      )}
      <div className="feed-news-main">
        <div className="feed-news-meta">
          {showSourceTag ? (
            <span className="feed-source-label" style={sourceStyle}>
              {isTwitterItem(item) ? `𝕏 ${sourceLabel}` : sourceLabel}
            </span>
          ) : null}
          {item.publish_time ? (
            <span className={showSourceTag ? "feed-meta-dot" : undefined}>
              <TimeDisplay time={item.publish_time} />
            </span>
          ) : null}
          {item.author ? (
            <span className={isTwitterItem(item) ? "feed-twitter-author" : "feed-meta-dot"}>
              {isTwitterItem(item) ? `@${item.author}` : item.author}
            </span>
          ) : null}
          {isFresh && layout === "stream" ? (
            <span className="feed-fresh-badge">最新</span>
          ) : null}
          {"otherSources" in item && Array.isArray(item.otherSources) && item.otherSources.length > 0 ? (
            <Tooltip title={`该事件亦由 ${item.otherSources.join("、")} 交叉报道`}>
              <span className="feed-cluster-badge">
                +{item.otherSources.length} 来源
              </span>
            </Tooltip>
          ) : null}
        </div>

        {item.url ? (
          <a className="feed-news-title" href={item.url} target="_blank" rel="noopener noreferrer">
            {titleContent}
          </a>
        ) : (
          <span className="feed-news-title">{titleContent}</span>
        )}

        {item.content ? <p className="feed-news-content">{item.content}</p> : null}
        {item.image_url ? <MediaPreview imageUrl={item.image_url} title={item.title} /> : null}

        {item.read_count > 0 || item.comment_count > 0 ? (
          <div className="feed-item-stats">
            {item.read_count > 0 ? (
              <span>{isTwitterItem(item) ? "浏览" : "阅读"} {item.read_count.toLocaleString()}</span>
            ) : null}
            {item.comment_count > 0 ? (
              <span>{isTwitterItem(item) ? "回复" : "评论"} {item.comment_count.toLocaleString()}</span>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
