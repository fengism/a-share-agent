import { useRef, useState } from "react";
import {
  CheckOutlined,
  CopyOutlined,
  DownloadOutlined,
  FileImageOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { Button, Modal, Typography, message } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useColors, useTokens } from "../../../styles/ui";
import { formatMarketDateTime, marketDateStamp } from "../../../utils/marketTime";

const { Text } = Typography;

interface ResearchCardExportModalProps {
  open: boolean;
  onClose: () => void;
  content: string;
  messageId: string;
}

export function ResearchCardExportModal({
  open,
  onClose,
  content,
  messageId,
}: ResearchCardExportModalProps) {
  const c = useColors();
  const t = useTokens();
  const cardRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [copied, setCopied] = useState(false);

  const captureCanvas = async () => {
    if (!cardRef.current) return null;
    const { default: html2canvas } = await import("html2canvas-pro");
    return html2canvas(cardRef.current, {
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
      link.download = `AI投研快报_${messageId.slice(0, 8)}_${marketDateStamp()}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      message.success("投研卡片图片已保存");
    } catch {
      message.error("生成图片失败，请重试");
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
          setCopied(true);
          message.success("投研长图已复制到剪贴板，可直接粘贴分享！");
          setTimeout(() => setCopied(false), 2000);
        } catch {
          message.info("当前浏览器环境不支持直接复制图片，请使用保存图片");
        }
      });
    } catch {
      message.error("复制图片失败");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileImageOutlined style={{ color: c.primary }} />
          <span>导出投研报告卡片</span>
        </div>
      }
      open={open}
      onCancel={onClose}
      width={680}
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
          {copied ? "已复制" : "复制长图"}
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
      <div
        style={{
          maxHeight: "65vh",
          overflowY: "auto",
          padding: "12px 4px",
        }}
      >
        <div
          ref={cardRef}
          style={{
            background: c.cardBg,
            border: `1px solid ${c.border}`,
            borderRadius: t.radius.lg,
            padding: "var(--c-pad-card, 16px 18px)",
            boxShadow: t.shadow.sm,
            color: c.textPrimary,
          }}
        >
          {/* 海报头部 */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              paddingBottom: 16,
              borderBottom: `1px solid ${c.border}`,
              marginBottom: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: t.radius.md,
                  background: `linear-gradient(135deg, ${c.primary}33, ${c.accent}44)`,
                  border: `1px solid ${c.primary}66`,
                  display: "grid",
                  placeItems: "center",
                  color: c.primary,
                  fontSize: 18,
                }}
              >
                <RobotOutlined />
              </div>
              <div>
                <strong style={{ fontSize: 16, color: c.textPrimary, display: "block" }}>
                  A股智能投研快报
                </strong>
                <span style={{ fontSize: 11, color: c.textMuted }}>
                  AI Research Insights & Intelligence
                </span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <span style={{ fontSize: 11, color: c.textSecondary, fontFamily: "monospace" }}>
                {formatMarketDateTime(new Date())}
              </span>
            </div>
          </div>

          {/* 正文 */}
          <div className="chat-markdown" style={{ fontSize: 13.5, lineHeight: 1.6 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>

          {/* 海报尾部 */}
          <div
            style={{
              marginTop: 20,
              paddingTop: 14,
              borderTop: `1px dashed ${c.border}`,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Text type="secondary" style={{ fontSize: 11 }}>
              ⚠️ 免责声明：本分析基于市场客观数据由 AI 生成，仅供投研交流，不构成买卖依据。
            </Text>
            <span style={{ fontSize: 11, color: c.primary, fontWeight: 600 }}>
              AI 选股助手
            </span>
          </div>
        </div>
      </div>
    </Modal>
  );
}
