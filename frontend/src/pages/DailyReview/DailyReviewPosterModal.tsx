import { useRef, useState } from "react";
import {
  CheckOutlined,
  CopyOutlined,
  DownloadOutlined,
  FileImageOutlined,
} from "@ant-design/icons";
import { Button, Modal, Tag, message } from "antd";
import { useCopyFeedback } from "../../hooks/useCopyFeedback";
import { useColors, useTokens } from "../../styles/ui";
import { formatSignedPct, type DailyReviewPayload, type ReviewHeadline } from "./reviewView";
import { analyzeSentiment } from "./sentimentAnalyzer";

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
  const t = useTokens();
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
  const indexTone = (safeHeadline.indexChangePct ?? 0) >= 0 ? c.up : c.down;

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
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileImageOutlined style={{ color: c.primary }} />
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
      <div style={{ maxHeight: "72vh", overflowY: "auto", padding: "8px 4px" }}>
        <div
          ref={posterRef}
          style={{
            background: c.cardBg,
            border: `1px solid ${c.border}`,
            borderRadius: t.radius.lg,
            padding: "24px 22px",
            boxShadow: t.shadow.sm,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: `1px solid ${c.border}`, paddingBottom: 14 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary }}>每日市场复盘战报</span>
                <Tag color="blue" style={{ margin: 0, fontSize: 11, fontFamily: "var(--c-font-mono)" }}>
                  {review.date || "TODAY"}
                </Tag>
              </div>
              <div style={{ fontSize: 12, color: c.textMuted, marginTop: 4 }}>
                A-Share Agent · 智能多因子情绪与大盘复盘
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: c.textMuted }}>定盘状态</div>
              <Tag color="cyan" style={{ margin: 0, marginTop: 2 }}>已收盘定盘</Tag>
            </div>
          </div>

          {/* Title & Summary */}
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: c.textPrimary, marginBottom: 6 }}>
              {review.title || "全市场行情全景复盘"}
            </div>
            <p style={{ fontSize: 13, color: c.textSecondary, lineHeight: 1.6, margin: 0 }}>
              {review.market_summary}
            </p>
          </div>

          {/* Sentiment Gauge Box */}
          <div
            style={{
              padding: "14px 16px",
              borderRadius: t.radius.md,
              border: `1px solid color-mix(in srgb, ${sentiment.color} 30%, ${c.border})`,
              background: `color-mix(in srgb, ${sentiment.color} 7%, ${c.cardBg})`,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 20 }}>{sentiment.zoneIcon}</span>
                <span style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--c-font-mono)", color: sentiment.color }}>
                  {sentiment.temperature}°C
                </span>
                <Tag
                  style={{
                    background: `color-mix(in srgb, ${sentiment.color} 20%, transparent)`,
                    color: sentiment.color,
                    fontWeight: 600,
                    margin: 0,
                  }}
                >
                  {sentiment.zoneLabel}
                </Tag>
              </div>

              <div style={{ fontSize: 12 }}>
                <span style={{ color: c.textSecondary }}>战术：</span>
                <strong style={{ color: sentiment.color }}>{sentiment.tactics}</strong>
              </div>
            </div>

            {/* 5 Factors Progress */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, textAlign: "center", fontSize: 11 }}>
              <div>
                <span style={{ color: c.textMuted }}>上涨广度</span>
                <div style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)", marginTop: 2 }}>{sentiment.factors.breadth}</div>
              </div>
              <div>
                <span style={{ color: c.textMuted }}>动量积聚</span>
                <div style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)", marginTop: 2 }}>{sentiment.factors.momentum}</div>
              </div>
              <div>
                <span style={{ color: c.textMuted }}>资金量能</span>
                <div style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)", marginTop: 2 }}>{sentiment.factors.turnover}</div>
              </div>
              <div>
                <span style={{ color: c.textMuted }}>结构稳定</span>
                <div style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)", marginTop: 2 }}>{sentiment.factors.stability}</div>
              </div>
              <div>
                <span style={{ color: c.textMuted }}>周期定位</span>
                <div style={{ fontWeight: 600, fontFamily: "var(--c-font-mono)", marginTop: 2 }}>{sentiment.factors.cycle}</div>
              </div>
            </div>
          </div>

          {/* Key Indicators Grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 10,
            }}
          >
            <div style={{ padding: "8px 10px", background: c.hoverBg, borderRadius: 6, textAlign: "center" }}>
              <div style={{ fontSize: 11, color: c.textSecondary }}>涨停家数</div>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "var(--c-font-mono)", marginTop: 2, color: c.up }}>
                {safeHeadline.limitUpCount ?? "—"}
              </div>
            </div>
            <div style={{ padding: "8px 10px", background: c.hoverBg, borderRadius: 6, textAlign: "center" }}>
              <div style={{ fontSize: 11, color: c.textSecondary }}>炸板率</div>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "var(--c-font-mono)", marginTop: 2, color: c.warning }}>
                {safeHeadline.breakRate != null ? `${safeHeadline.breakRate.toFixed(1)}%` : "—"}
              </div>
            </div>
            <div style={{ padding: "8px 10px", background: c.hoverBg, borderRadius: 6, textAlign: "center" }}>
              <div style={{ fontSize: 11, color: c.textSecondary }}>{safeHeadline.indexName || "指数表现"}</div>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: "var(--c-font-mono)", marginTop: 2, color: indexTone }}>
                {formatSignedPct(safeHeadline.indexChangePct)}
              </div>
            </div>
            <div style={{ padding: "8px 10px", background: c.hoverBg, borderRadius: 6, textAlign: "center" }}>
              <div style={{ fontSize: 11, color: c.textSecondary }}>情绪阶段</div>
              <div style={{ fontSize: 14, fontWeight: 700, marginTop: 2, color: sentiment.color }}>
                {safeHeadline.stage || "震荡整理"}
              </div>
            </div>
          </div>

          {/* Sentiment Mood Summary */}
          {moodSummary ? (
            <div style={{ fontSize: 12, color: c.textSecondary, background: c.hoverBg, padding: "8px 12px", borderRadius: 6 }}>
              <span style={{ color: c.primary, fontWeight: 600, marginRight: 6 }}>市场定性：</span>
              <span>{moodSummary}</span>
            </div>
          ) : null}

          {/* Footer Branding */}
          <div
            style={{
              borderTop: `1px dashed ${c.border}`,
              paddingTop: 12,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: 11,
              color: c.textMuted,
            }}
          >
            <span>由 A-Share Agent 量化投研生成</span>
            <span>复盘日期：{review.date}</span>
          </div>
        </div>
      </div>
    </Modal>
  );
}
