import { useRef, useState } from "react";
import {
  CheckOutlined,
  CopyOutlined,
  DownloadOutlined,
  FileImageOutlined,
} from "@ant-design/icons";
import { Button, Modal, Tag, message } from "antd";
import { useCopyFeedback } from "../../hooks/useCopyFeedback";
import { useColors } from "../../styles/ui";
import { formatSignedPct, type DailyReviewPayload, type ReviewHeadline } from "./reviewView";
import { analyzeSentiment } from "./sentimentAnalyzer";
import "./daily-review-poster.css";

export interface DailyReviewPosterModalProps {
  open: boolean;
  onClose: () => void;
  review: DailyReviewPayload;
  headline: ReviewHeadline | null;
  moodSummary: string;
}

export default function DailyReviewPosterModal({
  open,
  onClose,
  review,
  headline,
  moodSummary,
}: DailyReviewPosterModalProps) {
  const c = useColors();
  const posterRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const { copied, markCopied } = useCopyFeedback(2000);

  const fallbackHeadline: ReviewHeadline = {
    quality: "complete",
    generation: "ai",
    stage: headline?.stage || "修复回暖",
    indexName: headline?.indexName || "上证指数",
    indexChangePct: headline?.indexChangePct ?? 0,
    limitUpCount: headline?.limitUpCount ?? null,
    breakRate: headline?.breakRate ?? null,
    checkHit: headline?.checkHit ?? null,
    checkTotal: headline?.checkTotal ?? null,
  };

  const safeHeadline = headline ?? fallbackHeadline;
  const sentiment = analyzeSentiment(review, safeHeadline);
  const isIndexUp = (safeHeadline.indexChangePct ?? 0) >= 0;

  const sentimentBoxStyle: React.CSSProperties = {
    borderColor: `color-mix(in srgb, ${sentiment.color} 30%, var(--c-border))`,
    backgroundColor: `color-mix(in srgb, ${sentiment.color} 7%, var(--c-card-bg))`,
  };
  const sentimentTagStyle: React.CSSProperties = {
    backgroundColor: `color-mix(in srgb, ${sentiment.color} 20%, transparent)`,
    color: sentiment.color,
  };
  const sentimentColorStyle: React.CSSProperties = {
    color: sentiment.color,
  };

  const captureCanvas = async () => {
    if (!posterRef.current) return null;
    const { default: html2canvas } = await import("html2canvas-pro");
    return html2canvas(posterRef.current, {
      backgroundColor: c.pageBg,
      scale: 2,
      useCORS: true,
      logging: false,
    });
  };

  const handleDownloadImage = async () => {
    try {
      setIsExporting(true);
      const canvas = await captureCanvas();
      if (!canvas) return;

      const link = document.createElement("a");
      link.download = `市场复盘海报_${review.date || "当日"}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      void message.success("复盘海报图片已保存");
    } catch {
      void message.error("生成海报失败，请重试");
    } finally {
      setIsExporting(false);
    }
  };

  const handleCopyImage = async () => {
    try {
      setIsExporting(true);
      const canvas = await captureCanvas();
      if (!canvas) return;

      canvas.toBlob(async (blob) => {
        if (!blob) return;
        try {
          await navigator.clipboard.write([
            new ClipboardItem({ "image/png": blob }),
          ]);
          markCopied();
          void message.success("复盘海报已复制到剪贴板，可直接粘贴分享！");
        } catch {
          void message.info("当前浏览器环境不支持直接复制图片，请使用保存图片");
        }
      });
    } catch {
      void message.error("复制图片失败");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Modal
      title={(
        <div className="daily-review-poster__modal-header">
          <FileImageOutlined className="daily-review-poster__modal-icon" />
          <span>生成复盘战报长图</span>
        </div>
      )}
      open={open}
      onCancel={onClose}
      width={600}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        <Button
          key="copy"
          icon={copied ? <CheckOutlined /> : <CopyOutlined />}
          onClick={handleCopyImage}
          loading={isExporting}
        >
          {copied ? "已复制" : "复制海报"}
        </Button>,
        <Button
          key="download"
          type="primary"
          icon={<DownloadOutlined />}
          onClick={handleDownloadImage}
          loading={isExporting}
        >
          保存图片 (PNG)
        </Button>,
      ]}
    >
      <div className="daily-review-poster__scroll">
        <div ref={posterRef} className="daily-review-poster__card">
          {/* Header */}
          <div className="daily-review-poster__header">
            <div>
              <div className="daily-review-poster__header-title-row">
                <span className="daily-review-poster__header-title">每日市场复盘战报</span>
                <Tag color="blue" className="daily-review-poster__header-date-tag">
                  {review.date || "TODAY"}
                </Tag>
              </div>
              <div className="daily-review-poster__header-sub">
                A-Share Agent · 智能多因子情绪与大盘复盘
              </div>
            </div>
            <div className="daily-review-poster__header-status">
              <div className="daily-review-poster__header-status-label">定盘状态</div>
              <Tag color="cyan" className="daily-review-poster__header-status-tag">已收盘定盘</Tag>
            </div>
          </div>

          {/* Title & Summary */}
          <div>
            <div className="daily-review-poster__title">
              {review.title || "全市场行情全景复盘"}
            </div>
            <p className="daily-review-poster__summary">
              {review.market_summary}
            </p>
          </div>

          {/* Sentiment Gauge Box */}
          <div className="daily-review-poster__sentiment-box" style={sentimentBoxStyle}>
            <div className="daily-review-poster__sentiment-header">
              <div className="daily-review-poster__sentiment-badge">
                <span className="daily-review-poster__sentiment-icon">{sentiment.zoneIcon}</span>
                <span className="daily-review-poster__sentiment-temp" style={sentimentColorStyle}>
                  {sentiment.temperature}°C
                </span>
                <Tag
                  className="daily-review-poster__sentiment-tag"
                  style={sentimentTagStyle}
                >
                  {sentiment.zoneLabel}
                </Tag>
              </div>

              <div className="daily-review-poster__sentiment-tactics">
                <span className="daily-review-poster__sentiment-tactics-label">战术：</span>
                <strong style={sentimentColorStyle}>{sentiment.tactics}</strong>
              </div>
            </div>

            {/* 5 Factors Progress */}
            <div className="daily-review-poster__factors-grid">
              <div>
                <span className="daily-review-poster__factor-label">上涨广度</span>
                <div className="daily-review-poster__factor-value">{sentiment.factors.breadth}</div>
              </div>
              <div>
                <span className="daily-review-poster__factor-label">动量积聚</span>
                <div className="daily-review-poster__factor-value">{sentiment.factors.momentum}</div>
              </div>
              <div>
                <span className="daily-review-poster__factor-label">资金量能</span>
                <div className="daily-review-poster__factor-value">{sentiment.factors.turnover}</div>
              </div>
              <div>
                <span className="daily-review-poster__factor-label">结构稳定</span>
                <div className="daily-review-poster__factor-value">{sentiment.factors.stability}</div>
              </div>
              <div>
                <span className="daily-review-poster__factor-label">周期定位</span>
                <div className="daily-review-poster__factor-value">{sentiment.factors.cycle}</div>
              </div>
            </div>
          </div>

          {/* Key Indicators Grid */}
          <div className="daily-review-poster__indicators-grid">
            <div className="daily-review-poster__indicator-card">
              <div className="daily-review-poster__indicator-label">涨停家数</div>
              <div className="daily-review-poster__indicator-value financial-num u-text-up">
                {safeHeadline.limitUpCount ?? "—"}
              </div>
            </div>
            <div className="daily-review-poster__indicator-card">
              <div className="daily-review-poster__indicator-label">炸板率</div>
              <div className="daily-review-poster__indicator-value financial-num u-text-warning">
                {safeHeadline.breakRate != null ? `${safeHeadline.breakRate.toFixed(1)}%` : "—"}
              </div>
            </div>
            <div className="daily-review-poster__indicator-card">
              <div className="daily-review-poster__indicator-label">{safeHeadline.indexName || "指数表现"}</div>
              <div className={`daily-review-poster__indicator-value financial-num ${isIndexUp ? "u-text-up" : "u-text-down"}`}>
                {formatSignedPct(safeHeadline.indexChangePct)}
              </div>
            </div>
            <div className="daily-review-poster__indicator-card">
              <div className="daily-review-poster__indicator-label">情绪阶段</div>
              <div className="daily-review-poster__indicator-value" style={sentimentColorStyle}>
                {safeHeadline.stage || "震荡整理"}
              </div>
            </div>
          </div>

          {/* Sentiment Mood Summary */}
          {moodSummary ? (
            <div className="daily-review-poster__mood-box">
              <span className="daily-review-poster__mood-prefix">市场定性：</span>
              <span>{moodSummary}</span>
            </div>
          ) : null}

          {/* Footer Branding */}
          <div className="daily-review-poster__footer">
            <span>由 A-Share Agent 量化投研生成</span>
            <span>复盘日期：{review.date}</span>
          </div>
        </div>
      </div>
    </Modal>
  );
}
