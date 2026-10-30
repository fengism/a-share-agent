import { useRef, useState } from "react";
import {
  BankOutlined,
  CheckOutlined,
  CopyOutlined,
  DownloadOutlined,
  FileImageOutlined,
  GlobalOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Modal, Tag, Typography, message } from "antd";
import { useColors, useTokens } from "../../styles/ui";
import type { StockBasicInfo } from "../../types/stock";
import { formatNumberWithSeparators } from "../../utils/format";
import { formatMarketDateTime, marketDateStamp } from "../../utils/marketTime";
import type { StockHeaderTapeData } from "./StockHeaderCard";

const { Title, Text } = Typography;

interface StockSnapshotModalProps {
  open: boolean;
  onClose: () => void;
  info: Partial<StockBasicInfo> & { code: string; name: string };
  market?: "cn" | "hk";
  englishName?: string | null;
  changePct?: number | null;
  tape?: StockHeaderTapeData | null;
}

function formatLargeAmount(val: number | null | undefined): string {
  if (val == null) return "-";
  if (Math.abs(val) >= 1e12) return `${(val / 1e12).toFixed(2)}万亿`;
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(2);
}

export default function StockSnapshotModal({
  open,
  onClose,
  info,
  market = "cn",
  englishName,
  changePct,
  tape,
}: StockSnapshotModalProps) {
  const c = useColors();
  const t = useTokens();
  const cardRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [copied, setCopied] = useState(false);

  const isHK = market === "hk";
  const currencySymbol = isHK ? "HK$" : "¥";
  const industry = info.first_industry?.name;

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
      link.download = `个股速览_${info.code}_${info.name}_${marketDateStamp()}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      void message.success("个股快报卡片图片已保存");
    } catch {
      void message.error("生成图片失败，请重试");
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
          void message.success("个股速览卡片已复制到剪贴板，可直接粘贴分享！");
          setTimeout(() => setCopied(false), 2000);
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

  const priceColor =
    changePct == null || changePct === 0
      ? c.textPrimary
      : changePct > 0
      ? c.up
      : c.down;

  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileImageOutlined style={{ color: c.primary }} />
          <span>导出个股速览卡片</span>
        </div>
      }
      open={open}
      onCancel={onClose}
      width={640}
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
          {copied ? "已复制" : "复制卡片图片"}
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
      <div style={{ maxHeight: "68vh", overflowY: "auto", padding: "8px 4px" }}>
        <div
          ref={cardRef}
          style={{
            background: c.cardBg,
            border: `1px solid ${c.border}`,
            borderRadius: t.radius.lg,
            padding: "var(--c-pad-card, 16px 18px)",
            boxShadow: t.shadow.sm,
            color: c.textPrimary,
            fontFamily: "var(--c-font-sans)",
          }}
        >
          {/* Header Branding */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: `1px solid ${c.border}`,
              paddingBottom: 14,
              marginBottom: 18,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 6,
                  background: `linear-gradient(135deg, ${c.primary}, ${c.up})`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                }}
              >
                <ThunderboltOutlined style={{ fontSize: 16 }} />
              </div>
              <span style={{ fontWeight: "var(--c-weight-bold)", fontSize: 15, letterSpacing: 0.5 }}>
                A-Share Agent · 智能投研
              </span>
            </div>
            <Text style={{ fontSize: 12, color: c.textSecondary }}>
              {formatMarketDateTime(new Date())}
            </Text>
          </div>

          {/* Stock Identity */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span style={{ color: c.primary, fontSize: 18 }}>
                  {isHK ? <GlobalOutlined /> : <BankOutlined />}
                </span>
                <Title level={3} style={{ margin: 0, fontWeight: "var(--c-weight-bold)" }}>
                  {info.name || info.code}
                </Title>
                <Tag style={{ fontFamily: "var(--c-font-mono)", fontSize: 14, margin: 0 }}>
                  {info.code}
                </Tag>
                {englishName && <Text type="secondary" style={{ fontSize: 12 }}>{englishName}</Text>}
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                {isHK ? (
                  <>
                    <Tag color="blue">港股主板</Tag>
                    <Tag>港币 (HKD)</Tag>
                  </>
                ) : (
                  <>
                    {industry && <Tag color="blue">{industry}</Tag>}
                    {(info.concepts ?? []).slice(0, 4).map((c) => (
                      <Tag key={c.name}>{c.name}</Tag>
                    ))}
                  </>
                )}
              </div>
            </div>

            {/* Price Quote */}
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 28, fontWeight: "var(--c-weight-bold)", fontFamily: "var(--c-font-mono)", color: priceColor, lineHeight: 1.1 }}>
                {info.current_price != null ? `${currencySymbol}${info.current_price.toFixed(2)}` : "-"}
              </div>
              <div style={{ fontSize: 13, color: priceColor, marginTop: 4, fontFamily: "var(--c-font-mono)" }}>
                {changePct != null ? `${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%` : "-"}
                {info.turnover_pct != null ? ` · 换手 ${info.turnover_pct.toFixed(2)}%` : ""}
              </div>
            </div>
          </div>

          {/* Tape & 52-Week Range */}
          {tape && (
            <div
              style={{
                background: c.hoverBg,
                borderRadius: 8,
                padding: "var(--c-pad-inset, 7px 12px)",
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(90px, 1fr))",
                gap: 8,
                fontSize: 12,
                marginBottom: 16,
              }}
            >
              <div>
                <span style={{ color: c.textSecondary }}>今开: </span>
                <strong style={{ fontFamily: "var(--c-font-mono)" }}>{tape.open != null ? formatNumberWithSeparators(tape.open) : "-"}</strong>
              </div>
              <div>
                <span style={{ color: c.textSecondary }}>最高: </span>
                <strong style={{ fontFamily: "var(--c-font-mono)", color: tape.high != null && tape.prevClose != null && tape.high > tape.prevClose ? c.up : undefined }}>
                  {tape.high != null ? formatNumberWithSeparators(tape.high) : "-"}
                </strong>
              </div>
              <div>
                <span style={{ color: c.textSecondary }}>最低: </span>
                <strong style={{ fontFamily: "var(--c-font-mono)", color: tape.low != null && tape.prevClose != null && tape.low < tape.prevClose ? c.down : undefined }}>
                  {tape.low != null ? formatNumberWithSeparators(tape.low) : "-"}
                </strong>
              </div>
              <div>
                <span style={{ color: c.textSecondary }}>成交额: </span>
                <strong style={{ fontFamily: "var(--c-font-mono)" }}>{formatLargeAmount(tape.amount)}</strong>
              </div>
              {tape.amplitude != null && (
                <div>
                  <span style={{ color: c.textSecondary }}>日振幅: </span>
                  <strong style={{ fontFamily: "var(--c-font-mono)" }}>{tape.amplitude.toFixed(2)}%</strong>
                </div>
              )}
            </div>
          )}

          {/* 52-Week Range Bar */}
          {tape?.fiftyTwoWeekLow != null && tape?.fiftyTwoWeekHigh != null && tape.fiftyTwoWeekHigh > tape.fiftyTwoWeekLow && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "var(--c-pad-inset, 7px 12px)",
                background: c.hoverBg,
                borderRadius: 8,
                fontSize: 12,
                marginBottom: 16,
              }}
            >
              <span style={{ color: c.textSecondary }}>52周区间</span>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, maxWidth: 280, margin: "0 14px" }}>
                <span style={{ fontFamily: "var(--c-font-mono)", fontSize: 11, color: c.textSecondary }}>
                  {formatNumberWithSeparators(tape.fiftyTwoWeekLow)}
                </span>
                <div style={{ flex: 1, height: 6, background: c.border, borderRadius: 3, position: "relative", overflow: "hidden" }}>
                  {info.current_price != null && (
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        bottom: 0,
                        width: `${Math.max(0, Math.min(100, ((info.current_price - tape.fiftyTwoWeekLow) / (tape.fiftyTwoWeekHigh - tape.fiftyTwoWeekLow)) * 100))}%`,
                        background: c.primary,
                        borderRadius: 3,
                      }}
                    />
                  )}
                </div>
                <span style={{ fontFamily: "var(--c-font-mono)", fontSize: 11, color: c.textSecondary }}>
                  {formatNumberWithSeparators(tape.fiftyTwoWeekHigh)}
                </span>
              </div>
              <span style={{ color: c.primary, fontWeight: "var(--c-weight-semibold)", fontSize: 12 }}>
                {info.current_price != null
                  ? `位阶 ${Math.round(((info.current_price - tape.fiftyTwoWeekLow) / (tape.fiftyTwoWeekHigh - tape.fiftyTwoWeekLow)) * 100)}%`
                  : "-"}
              </span>
            </div>
          )}

          {/* Core Valuation Metrics */}
          {!isHK && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 10,
                marginBottom: 18,
              }}
            >
              <div style={{ padding: "var(--c-pad-inset, 7px 12px)", background: c.hoverBg, borderRadius: 6, textAlign: "center" }}>
                <div style={{ fontSize: 11, color: c.textSecondary }}>总市值</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2, fontFamily: "var(--c-font-mono)" }}>
                  {formatLargeAmount(info.market_cap)}
                </div>
              </div>
              <div style={{ padding: "var(--c-pad-inset, 7px 12px)", background: c.hoverBg, borderRadius: 6, textAlign: "center" }}>
                <div style={{ fontSize: 11, color: c.textSecondary }}>市盈率(TTM)</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2, fontFamily: "var(--c-font-mono)" }}>
                  {info.pe_ttm != null ? info.pe_ttm.toFixed(2) : "-"}
                </div>
              </div>
              <div style={{ padding: "var(--c-pad-inset, 7px 12px)", background: c.hoverBg, borderRadius: 6, textAlign: "center" }}>
                <div style={{ fontSize: 11, color: c.textSecondary }}>市净率(PB)</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2, fontFamily: "var(--c-font-mono)" }}>
                  {info.pb != null ? info.pb.toFixed(2) : "-"}
                </div>
              </div>
            </div>
          )}

          {/* Footer Disclaimer */}
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
            <span>由 A-Share Agent 智能投研引擎生成</span>
            <span>仅供学术研究与量化参考 · 不构成投资建议</span>
          </div>
        </div>
      </div>
    </Modal>
  );
}
