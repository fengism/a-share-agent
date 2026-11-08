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
import { useCopyFeedback } from "../../hooks/useCopyFeedback";
import { useColors } from "../../styles/ui";
import type { StockBasicInfo } from "../../types/stock";
import { formatNumberWithSeparators } from "../../utils/format";
import { formatMarketDateTime, marketDateStamp } from "../../utils/marketTime";
import type { StockHeaderTapeData } from "./StockHeaderCard";
import "./styles/snapshot-modal.css";

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
  const cardRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const { copied, markCopied } = useCopyFeedback(2000);

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
          markCopied();
          void message.success("个股速览卡片已复制到剪贴板，可直接粘贴分享！");
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

  const priceCls =
    changePct == null || changePct === 0
      ? "u-text-primary"
      : changePct > 0
      ? "u-text-up"
      : "u-text-down";

  const highTone =
    tape?.high != null && tape.prevClose != null && tape.high > tape.prevClose ? "u-text-up" : "";
  const lowTone =
    tape?.low != null && tape.prevClose != null && tape.low < tape.prevClose ? "u-text-down" : "";

  const rangePercent =
    tape?.fiftyTwoWeekLow != null &&
    tape?.fiftyTwoWeekHigh != null &&
    tape.fiftyTwoWeekHigh > tape.fiftyTwoWeekLow &&
    info.current_price != null
      ? Math.max(0, Math.min(100, ((info.current_price - tape.fiftyTwoWeekLow) / (tape.fiftyTwoWeekHigh - tape.fiftyTwoWeekLow)) * 100))
      : 0;
  const rangeFillStyle: React.CSSProperties = {
    width: `${rangePercent}%`,
  };

  return (
    <Modal
      title={
        <div className="stock-snapshot__modal-header">
          <FileImageOutlined className="stock-snapshot__modal-icon" />
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
      <div className="stock-snapshot__scroll">
        <div ref={cardRef} className="stock-snapshot__card">
          {/* Header Branding */}
          <div className="stock-snapshot__header">
            <div className="stock-snapshot__brand">
              <div className="stock-snapshot__brand-icon">
                <ThunderboltOutlined />
              </div>
              <span className="stock-snapshot__brand-text">
                A-Share Agent · 智能投研
              </span>
            </div>
            <Text className="stock-snapshot__timestamp">
              {formatMarketDateTime(new Date())}
            </Text>
          </div>

          {/* Stock Identity */}
          <div className="stock-snapshot__identity-row">
            <div>
              <div className="stock-snapshot__name-row">
                <span className="stock-snapshot__market-icon">
                  {isHK ? <GlobalOutlined /> : <BankOutlined />}
                </span>
                <Title level={3} className="stock-snapshot__title">
                  {info.name || info.code}
                </Title>
                <Tag className="stock-snapshot__code-tag">
                  {info.code}
                </Tag>
                {englishName && <Text type="secondary" className="stock-snapshot__english-name">{englishName}</Text>}
              </div>
              <div className="stock-snapshot__tags-row">
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
            <div className="stock-snapshot__price-col">
              <div className={`stock-snapshot__price ${priceCls}`}>
                {info.current_price != null ? `${currencySymbol}${info.current_price.toFixed(2)}` : "-"}
              </div>
              <div className={`stock-snapshot__change-row ${priceCls}`}>
                {changePct != null ? `${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%` : "-"}
                {info.turnover_pct != null ? ` · 换手 ${info.turnover_pct.toFixed(2)}%` : ""}
              </div>
            </div>
          </div>

          {/* Tape & 52-Week Range */}
          {tape && (
            <div className="stock-snapshot__tape-grid">
              <div>
                <span className="stock-snapshot__tape-label">今开: </span>
                <strong className="stock-snapshot__tape-val">{tape.open != null ? formatNumberWithSeparators(tape.open) : "-"}</strong>
              </div>
              <div>
                <span className="stock-snapshot__tape-label">最高: </span>
                <strong className={`stock-snapshot__tape-val ${highTone}`}>
                  {tape.high != null ? formatNumberWithSeparators(tape.high) : "-"}
                </strong>
              </div>
              <div>
                <span className="stock-snapshot__tape-label">最低: </span>
                <strong className={`stock-snapshot__tape-val ${lowTone}`}>
                  {tape.low != null ? formatNumberWithSeparators(tape.low) : "-"}
                </strong>
              </div>
              <div>
                <span className="stock-snapshot__tape-label">成交额: </span>
                <strong className="stock-snapshot__tape-val">{formatLargeAmount(tape.amount)}</strong>
              </div>
              {tape.amplitude != null && (
                <div>
                  <span className="stock-snapshot__tape-label">日振幅: </span>
                  <strong className="stock-snapshot__tape-val">{tape.amplitude.toFixed(2)}%</strong>
                </div>
              )}
            </div>
          )}

          {/* 52-Week Range Bar */}
          {tape?.fiftyTwoWeekLow != null && tape?.fiftyTwoWeekHigh != null && tape.fiftyTwoWeekHigh > tape.fiftyTwoWeekLow && (
            <div className="stock-snapshot__range-bar">
              <span className="stock-snapshot__tape-label">52周区间</span>
              <div className="stock-snapshot__range-middle">
                <span className="stock-snapshot__range-val">
                  {formatNumberWithSeparators(tape.fiftyTwoWeekLow)}
                </span>
                <div className="stock-snapshot__range-track">
                  {info.current_price != null && (
                    <div
                      className="stock-snapshot__range-fill"
                      style={rangeFillStyle}
                    />
                  )}
                </div>
                <span className="stock-snapshot__range-val">
                  {formatNumberWithSeparators(tape.fiftyTwoWeekHigh)}
                </span>
              </div>
              <span className="stock-snapshot__range-percent">
                {info.current_price != null
                  ? `位阶 ${Math.round(rangePercent)}%`
                  : "-"}
              </span>
            </div>
          )}

          {/* Core Valuation Metrics */}
          {!isHK && (
            <div className="stock-snapshot__metrics-grid">
              <div className="stock-snapshot__metric-card">
                <div className="stock-snapshot__metric-label">总市值</div>
                <div className="stock-snapshot__metric-val">
                  {formatLargeAmount(info.market_cap)}
                </div>
              </div>
              <div className="stock-snapshot__metric-card">
                <div className="stock-snapshot__metric-label">市盈率(TTM)</div>
                <div className="stock-snapshot__metric-val">
                  {info.pe_ttm != null ? info.pe_ttm.toFixed(2) : "-"}
                </div>
              </div>
              <div className="stock-snapshot__metric-card">
                <div className="stock-snapshot__metric-label">市净率(PB)</div>
                <div className="stock-snapshot__metric-val">
                  {info.pb != null ? info.pb.toFixed(2) : "-"}
                </div>
              </div>
            </div>
          )}

          {/* Footer Disclaimer */}
          <div className="stock-snapshot__footer">
            <span>由 A-Share Agent 智能投研引擎生成</span>
            <span>仅供学术研究与量化参考 · 不构成投资建议</span>
          </div>
        </div>
      </div>
    </Modal>
  );
}
