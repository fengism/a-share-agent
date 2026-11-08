import { useRef, useState } from "react";
import {
  CheckOutlined,
  CopyOutlined,
  DownloadOutlined,
  FileImageOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Divider, Modal, Row, Space, Tag, Typography, message } from "antd";
import type { NationalTeamResponse } from "../../../types/stock/market";
import { useColors } from "../../../styles/ui";
import { useCopyFeedback } from "../../../hooks/useCopyFeedback";

const { Text, Title } = Typography;

export interface NationalTeamReportModalProps {
  open: boolean;
  onClose: () => void;
  data?: NationalTeamResponse;
}

export default function NationalTeamReportModal({
  open,
  onClose,
  data,
}: NationalTeamReportModalProps) {
  const colors = useColors();
  const reportRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const { copied: imgCopied, markCopied: markImgCopied } = useCopyFeedback(2000);
  const { copied: textCopied, markCopied: markTextCopied } = useCopyFeedback(2000);

  if (!data) return null;

  const asOfDate = data.as_of_date || "最新";
  const supportScore = data.support_score?.score ?? 50;
  const supportLevel =
    supportScore >= 70
      ? { text: "高强度托底", color: colors.primary, tag: "blue" }
      : supportScore >= 50
      ? { text: "温和护盘", color: colors.warning, tag: "orange" }
      : { text: "常规运行", color: colors.textSecondary, tag: "default" };

  const netFlow1d = data.summary?.estimated_net_flow_1d_100m ?? 0;
  const totalAmount1d = data.summary?.total_amount_1d_100m ?? 0;
  const cumulativeFlow = data.summary?.cumulative_net_flow_100m ?? 0;
  const ytdFlow = data.summary?.ytd_net_flow_100m;

  // 异动放量 ETF
  const abnormalEtfs = (data.etfs || []).filter((e) => e.is_abnormal_volume);

  // 净买入 Top 3 ETF
  const topFlowEtfs = [...(data.etfs || [])]
    .filter((e) => (e.latest_estimated_net_flow_100m ?? 0) > 0)
    .sort((a, b) => (b.latest_estimated_net_flow_100m ?? 0) - (a.latest_estimated_net_flow_100m ?? 0))
    .slice(0, 3);

  // 板块资金拆解
  const latestDailyFlow = data.daily_flows?.[data.daily_flows.length - 1];
  const flowsByCategory = latestDailyFlow?.flows_by_category || {};
  const categoryLabels: Record<string, string> = {
    core_broad: "核心大盘 (300/50)",
    a500: "新质宽基 (中证A500)",
    growth: "中小成长 (500/1000/科创)",
    dividend: "红利防御",
  };

  // 盘中高频与百亿护盘信号衍生指标
  const intraday = data.intraday;
  const intradayTop3 = intraday?.minute?.table?.slice(0, 3) ?? [];
  const intradaySupportDays = intraday?.volume_signals?.support_days ?? [];
  const intradayRecentDays = intraday?.volume_signals?.recent_days ?? [];
  const intradaySupAvgAmt = intradaySupportDays.length > 0
    ? intradaySupportDays.reduce((acc, x) => acc + x.amount, 0) / intradaySupportDays.length
    : 0;
  const intradayRecAvgAmt = intradayRecentDays.length > 0
    ? intradayRecentDays.reduce((acc, x) => acc + x.amount, 0) / intradayRecentDays.length
    : 0;
  const intradayMultiple = intradayRecAvgAmt > 0 ? (intradaySupAvgAmt / intradayRecAvgAmt).toFixed(1) : null;

  // 截图生成 Canvas
  const captureCanvas = async () => {
    if (!reportRef.current) return null;
    const { default: html2canvas } = await import("html2canvas-pro");
    return html2canvas(reportRef.current, {
      backgroundColor: colors.pageBg,
      scale: 2,
      useCORS: true,
      logging: false,
    });
  };

  // 下载图片
  const handleDownloadImage = async () => {
    try {
      setIsExporting(true);
      const canvas = await captureCanvas();
      if (!canvas) return;

      const link = document.createElement("a");
      link.download = `国家队资金监测简报_${asOfDate}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      message.success("简报长图已成功保存！");
    } catch {
      message.error("生成长图失败，请重试");
    } finally {
      setIsExporting(false);
    }
  };

  // 复制图片到剪贴板
  const handleCopyImage = async () => {
    try {
      setIsExporting(true);
      const canvas = await captureCanvas();
      if (!canvas) return;

      canvas.toBlob(async (blob) => {
        if (!blob) return;
        try {
          await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
          markImgCopied();
          message.success("简报图片已复制到剪贴板，可直接粘贴分享！");
        } catch {
          message.info("当前浏览器不支持直接复制图片，请使用保存图片");
        }
      });
    } catch {
      message.error("复制图片失败");
    } finally {
      setIsExporting(false);
    }
  };

  // 生成 Markdown 格式文字研报
  const generateMarkdownReport = () => {
    const mdLines = [
      `# 📊 【国家队资金流向与托底研报】（截至 ${asOfDate}）`,
      "",
      `> 宏观研判：**${supportLevel.text}**（托底指数：${supportScore.toFixed(0)} / 100，近60日分位：${data.support_score?.percentile_60d != null ? (data.support_score.percentile_60d * 100).toFixed(0) + "%" : "-"}）`,
      "",
      "### 一、资金核心总量",
      `- **样本 ETF 总成交额**：${totalAmount1d.toFixed(2)} 亿元`,
      `- **1 日估算净申购**：${netFlow1d >= 0 ? "+" : ""}${netFlow1d.toFixed(2)} 亿元`,
      `- **区间累计净申购**：${cumulativeFlow >= 0 ? "+" : ""}${cumulativeFlow.toFixed(2)} 亿元`,
      ytdFlow != null ? `- **年初至今 (YTD) 净申购**：${ytdFlow >= 0 ? "+" : ""}${ytdFlow.toFixed(2)} 亿元` : "",
      `- **全市场样本覆盖**：${data.covered_etf_count} / ${data.total_etf_count} 只核心宽基 ETF`,
      "",
      "### 二、战术分类资金偏好",
      ...Object.entries(categoryLabels).map(([catKey, label]) => {
        const val = flowsByCategory[catKey] ?? 0;
        return `- **${label}**：${val >= 0 ? "+" : ""}${val.toFixed(2)} 亿元`;
      }),
      "",
      "### 三、主力异动标的",
      abnormalEtfs.length > 0
        ? `- **放量异动标的**：${abnormalEtfs.map((e) => `${e.name}(${e.code}) 成交${e.latest_amount_100m?.toFixed(1)}亿 (量比${e.volume_ratio}x)`).join("；")}`
        : "- **放量异动标的**：今日无显著超 1.8x 放量标的，资金流动相对温和。",
      topFlowEtfs.length > 0
        ? `- **净申购领跑 Top 3**：${topFlowEtfs.map((e) => `${e.name} (+${e.latest_estimated_net_flow_100m?.toFixed(2)} 亿元)`).join("，")}`
        : "",
      intraday ? "" : "",
      intraday ? "### 四、盘中高频特征与百亿护盘信号" : "",
      intraday && intradayTop3.length > 0
        ? `- **重点 ETF 成交领跑 Top 3**：${intradayTop3.map((e, idx) => `No.${idx + 1} ${e.name}(${e.code}) ${e.amount.toFixed(1)} 亿 (${e.pct > 0 ? "+" : ""}${e.pct.toFixed(2)}%)`).join("；")}`
        : "",
      intraday && intradayMultiple
        ? `- **百亿放量护盘中枢**：历史 ${intradaySupportDays.length} 个百亿护盘日均成交 ${intradaySupAvgAmt.toFixed(1)} 亿，为近 20 交易日常态中枢 (${intradayRecAvgAmt.toFixed(1)} 亿) 的 **${intradayMultiple} 倍**。`
        : "",
      "",
      "---",
      "*(注：申赎数据为「Δ份额 × 当日收盘价」工程估算值，成交额为二级市场实际成交；数据源：上交所/深交所/东方财富)*",
    ].filter(Boolean);

    return mdLines.join("\n");
  };

  const handleCopyMarkdown = async () => {
    try {
      const text = generateMarkdownReport();
      await navigator.clipboard.writeText(text);
      markTextCopied();
      message.success("文字研报已成功复制到剪贴板！");
    } catch {
      message.error("复制文本失败");
    }
  };

  return (
    <Modal
      title={
        <Space size={8} align="center">
          <FileImageOutlined className="u-text-primary" />
          <span>国家队宽基资金监测 · 日度简报长图</span>
          <Tag color="cyan">截至 {asOfDate}</Tag>
        </Space>
      }
      open={open}
      onCancel={onClose}
      width={720}
      footer={
        <div className="u-flex-between">
          <Button
            icon={textCopied ? <CheckOutlined /> : <CopyOutlined />}
            onClick={handleCopyMarkdown}
            data-testid="copy-markdown-btn"
          >
            {textCopied ? "文字已复制" : "复制文字研报"}
          </Button>
          <Space>
            <Button
              icon={imgCopied ? <CheckOutlined /> : <CopyOutlined />}
              onClick={handleCopyImage}
              loading={isExporting}
              data-testid="copy-image-btn"
            >
              {imgCopied ? "图片已复制" : "复制长图"}
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleDownloadImage}
              loading={isExporting}
              data-testid="download-image-btn"
            >
              保存长图 (PNG)
            </Button>
          </Space>
        </div>
      }
    >
      <div className="national-team-report-modal__scroll">
        {/* 长图容器 */}
        <div
          ref={reportRef}
          className="national-team-poster"
          data-testid="national-team-poster-content"
        >
          {/* 海报 Header */}
          <div className="national-team-poster__header">
            <div>
              <div className="national-team-poster__title-row">
                <span className="national-team-poster__icon">🏛️</span>
                <Title level={4} className="national-team-poster__title">
                  国家队宽基资金流向与托底监测
                </Title>
              </div>
              <Text type="secondary" className="national-team-poster__desc">
                每日跟踪主力机构申购赎回意图 · 捕捉宏观政策托底底牌
              </Text>
            </div>
            <div className="national-team-poster__meta">
              <Tag color="blue" className="u-m-0 u-text-semibold">
                {asOfDate}
              </Tag>
              <div className="national-team-poster__meta-sub">
                A-Share Agent
              </div>
            </div>
          </div>

          {/* 托底状态核心横幅 */}
          <div className="national-team-poster__support-banner">
            <div>
              <Text type="secondary" className="national-team-poster__support-title">今日托底意向诊断</Text>
              <div className="national-team-poster__support-row">
                <span className="national-team-poster__support-level" style={{ color: supportLevel.color }}>
                  {supportLevel.text}
                </span>
                <span className="national-team-poster__support-score">
                  托底指数：<strong className="u-text-primary">{supportScore.toFixed(0)}</strong> / 100
                </span>
              </div>
            </div>
            {data.support_score?.percentile_60d != null && (
              <Tag color={supportLevel.tag}>
                近 60 日分位：{(data.support_score.percentile_60d * 100).toFixed(0)}%
              </Tag>
            )}
          </div>

          {/* 四大核心资金指标 */}
          <Row gutter={[12, 12]} className="national-team-poster__section">
            <Col span={6}>
              <Card size="small" className="national-team-poster__metric-card">
                <Text type="secondary" className="national-team-poster__metric-title">样本成交总额</Text>
                <div className="national-team-poster__metric-val">
                  {totalAmount1d.toFixed(1)} <span className="national-team-poster__metric-unit">亿元</span>
                </div>
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" className="national-team-poster__metric-card">
                <Text type="secondary" className="national-team-poster__metric-title">1 日估算净申购</Text>
                <div
                  className="national-team-poster__metric-val"
                  style={{
                    color: netFlow1d > 0 ? colors.up : netFlow1d < 0 ? colors.down : colors.textPrimary,
                  }}
                >
                  {netFlow1d > 0 ? "+" : ""}{netFlow1d.toFixed(1)} <span className="national-team-poster__metric-unit">亿元</span>
                </div>
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" className="national-team-poster__metric-card">
                <Text type="secondary" className="national-team-poster__metric-title">区间累计净申购</Text>
                <div
                  className="national-team-poster__metric-val"
                  style={{
                    color: cumulativeFlow > 0 ? colors.up : cumulativeFlow < 0 ? colors.down : colors.textPrimary,
                  }}
                >
                  {cumulativeFlow > 0 ? "+" : ""}{cumulativeFlow.toFixed(1)} <span className="national-team-poster__metric-unit">亿元</span>
                </div>
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" className="national-team-poster__metric-card">
                <Text type="secondary" className="national-team-poster__metric-title">{ytdFlow != null ? "年初至今 (YTD)" : "监测覆盖数"}</Text>
                <div className="national-team-poster__metric-val">
                  {ytdFlow != null ? `${ytdFlow > 0 ? "+" : ""}${ytdFlow.toFixed(1)} 亿` : `${data.covered_etf_count} 只`}
                </div>
              </Card>
            </Col>
          </Row>

          {/* 战术分类资金偏好 */}
          <div className="national-team-poster__section">
            <div className="national-team-poster__section-title">
              <span>🎯</span>
              <span>战术分类资金偏好</span>
            </div>
            <Row gutter={[8, 8]}>
              {Object.entries(categoryLabels).map(([catKey, label]) => {
                const val = flowsByCategory[catKey] ?? 0;
                const isPositive = val > 0;
                return (
                  <Col span={12} key={catKey}>
                    <div className="national-team-poster__category-item">
                      <Text className="u-text-xs">{label}</Text>
                      <span
                        className="national-team-poster__category-val"
                        style={{
                          color: isPositive ? colors.up : val < 0 ? colors.down : colors.textSecondary,
                        }}
                      >
                        {isPositive ? "+" : ""}{val.toFixed(2)} 亿元
                      </span>
                    </div>
                  </Col>
                );
              })}
            </Row>
          </div>

          {/* 重点异动与旗舰标的 */}
          <div className="national-team-poster__section">
            <div className="national-team-poster__section-title">
              <ThunderboltOutlined className="u-text-warning" />
              <span>重点放量与净流入标的</span>
            </div>
            <div className="national-team-poster__box">
              {abnormalEtfs.length > 0 ? (
                <div className="national-team-poster__box-row">
                  <Tag color="orange" className="national-team-poster__tag">放量异动</Tag>
                  <span>
                    {abnormalEtfs
                      .map((e) => `${e.name} (${e.code} · 成交 ${e.latest_amount_100m?.toFixed(1)} 亿 · 量比 ${e.volume_ratio}x)`)
                      .join("；")}
                  </span>
                </div>
              ) : (
                <div className="national-team-poster__box-row u-text-muted">
                  今日样本池内无突破 1.8x 的异常放量标的，成交处于平稳区间。
                </div>
              )}
              {topFlowEtfs.length > 0 && (
                <div>
                  <Tag color="red" className="national-team-poster__tag">净买入领跑</Tag>
                  <span>
                    {topFlowEtfs
                      .map((e) => `${e.name} (+${e.latest_estimated_net_flow_100m?.toFixed(2)} 亿元)`)
                      .join("，")}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* 盘中高频与百亿护盘信号（若存在 intraday 数据） */}
          {intraday && (
            <div className="national-team-poster__section">
              <div className="national-team-poster__section-title">
                <span>⏱️</span>
                <span>盘中高频与百亿放量护盘信号</span>
              </div>
              <div className="national-team-poster__box">
                {intradayTop3.length > 0 && (
                  <div className="national-team-poster__box-row">
                    <Tag color="blue" className="national-team-poster__tag">盘中成交领跑</Tag>
                    <span>
                      {intradayTop3.map((item, i) => (
                        <span key={item.code} className="national-team-poster__item-gap">
                          <strong>No.{i + 1}</strong> {item.name} ({item.code}) · <strong className="u-text-primary">{item.amount.toFixed(1)} 亿</strong> ({item.pct > 0 ? "+" : ""}{item.pct.toFixed(2)}%)
                        </span>
                      ))}
                    </span>
                  </div>
                )}
                {intradayMultiple && (
                  <div className="u-text-secondary">
                    <Tag color="gold" className="national-team-poster__tag">护盘倍数标定</Tag>
                    历史百亿护盘日中枢 <strong>{intradaySupAvgAmt.toFixed(1)} 亿</strong> vs 近期常态 <strong>{intradayRecAvgAmt.toFixed(1)} 亿</strong> (放量达 <strong className="u-text-warning">{intradayMultiple}x</strong>)
                  </div>
                )}
              </div>
            </div>
          )}

          <Divider className="national-team-poster__divider" />

          {/* 底部规范说明 */}
          <div className="national-team-poster__footer">
            <div>
              数据口径：申赎估算额 = Δ份额 × 收盘价；二级市场成交额为交易所撮合实际值。
            </div>
            <div>A-Share Agent · 智能投研</div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
