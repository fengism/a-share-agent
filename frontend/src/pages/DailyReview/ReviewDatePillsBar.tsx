import { useMemo } from "react";
import { Button, Space, Typography } from "antd";
import { HistoryOutlined, RollbackOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useColors } from "../../styles/ui";
import "./review-date-pills.css";

const { Text } = Typography;

export interface ReviewDatePillsBarProps {
  currentDate: string;
  availableDates: string[];
  onSelectDate: (date: string) => void;
  disabled?: boolean;
}

function formatPillLabel(dateStr: string, isLatest: boolean): string {
  const d = dayjs(dateStr);
  const formatted = d.isValid() ? d.format("MM-DD") : dateStr;
  return isLatest ? `${formatted} (最新)` : formatted;
}

export default function ReviewDatePillsBar({
  currentDate,
  availableDates,
  onSelectDate,
  disabled = false,
}: ReviewDatePillsBarProps) {
  const c = useColors();

  // 整理并去重前 7 个可用历史交易日
  const uniqueDates = useMemo(() => {
    const set = new Set<string>();
    if (currentDate) set.add(currentDate);
    availableDates.forEach((d) => {
      if (d && typeof d === "string") set.add(d);
    });
    return Array.from(set).sort((a, b) => b.localeCompare(a)).slice(0, 7);
  }, [availableDates, currentDate]);

  const latestDate = uniqueDates[0] || currentDate;
  const isViewingHistorical = Boolean(currentDate && latestDate && currentDate !== latestDate);

  if (uniqueDates.length <= 1 && !isViewingHistorical) {
    return null;
  }

  return (
    <div className="review-date-pills-bar" role="navigation" aria-label="复盘历史日期快捷切换">
      <div className="review-date-pills-bar__inner">
        <Space size={8} wrap orientation="horizontal" align="center" className="review-date-pills-bar__pills">
          <span className="review-date-pills-bar__label">
            <HistoryOutlined style={{ marginRight: 4, color: c.primary }} />
            回看历史:
          </span>

          {uniqueDates.map((dateStr) => {
            const isSelected = dateStr === currentDate;
            const isLatest = dateStr === latestDate;
            return (
              <Button
                key={dateStr}
                size="small"
                type={isSelected ? "primary" : "default"}
                disabled={disabled}
                onClick={() => onSelectDate(dateStr)}
                className={`review-date-pill ${isSelected ? "review-date-pill--active" : ""}`}
                aria-current={isSelected ? "date" : undefined}
                title={`查看 ${dateStr} 市场复盘快照`}
              >
                {formatPillLabel(dateStr, isLatest)}
              </Button>
            );
          })}

          {isViewingHistorical ? (
            <Button
              size="small"
              type="dashed"
              disabled={disabled}
              onClick={() => onSelectDate(latestDate)}
              className="review-date-pill review-date-pill--return"
              icon={<RollbackOutlined />}
              title={`一键返回最新结算日 (${latestDate})`}
            >
              回最新 ➔
            </Button>
          ) : null}
        </Space>

        <div className="review-date-pills-bar__tip">
          <Text type="secondary" className="review-date-pills-bar__tip-text">
            ⏰ A股 15:45 初算 · 18:00 定盘
          </Text>
        </div>
      </div>
    </div>
  );
}
