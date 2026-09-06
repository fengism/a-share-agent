import { useState } from "react";
import { Button, Card, Modal } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import { useMarketIndexIntraday } from "../api/queries";
import IntradayChart from "../charts/IntradayChart";
import ChangeValue from "./ChangeValue";
import SectionDataState from "./SectionDataState";
import { useColors, useTokens } from "../styles/ui";
import { deriveIndexPrevClose } from "../utils/indexIntraday";
import "./index-intraday-card.css";

interface Props {
  symbol: string;
  name?: string;
  price?: number | null;
  changePct?: number | null;
  preClose?: number | null;
  height?: number;
}

export default function IndexIntradayCard({
  symbol,
  name,
  price,
  changePct,
  preClose,
  height = 420,
}: Props) {
  const c = useColors();
  const t = useTokens();
  const [expanded, setExpanded] = useState(false);
  const query = useMarketIndexIntraday(symbol);
  const items = query.data?.items ?? [];
  const hasData = items.length > 0;
  const latestItem = items.length > 0 ? items[items.length - 1] : undefined;
  const displayPrice = latestItem?.price ?? price;
  const referenceClose = query.data?.prev_close
    ?? preClose
    ?? deriveIndexPrevClose(price, changePct);

  return (
    <Card
      size="small"
      className="index-intraday-card"
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontWeight: Number(t.weight.semibold) }}>{name || symbol} 分时</span>
          {displayPrice != null && (
            <span style={{
              fontFamily: "var(--c-font-mono)",
              fontSize: t.font.sm,
              fontWeight: Number(t.weight.bold),
              color: changePct == null || changePct === 0 ? c.textPrimary : changePct > 0 ? c.up : c.down,
            }}>
              {displayPrice.toFixed(2)}
            </span>
          )}
          <ChangeValue value={changePct ?? null} showIcon />
        </div>
      }
      extra={
        <Button
          type="text"
          size="small"
          icon={<FullscreenOutlined />}
          aria-label="放大分时图"
          onClick={() => setExpanded(true)}
          style={{ color: c.textSecondary }}
        />
      }
      style={{ borderRadius: t.radius.md, border: `1px solid ${c.border}`, boxShadow: t.shadow.xs, height: "100%" }}
      styles={{ body: { padding: "12px 14px" } }}
    >
      <SectionDataState
        isLoading={query.isLoading && !hasData}
        error={hasData ? undefined : query.error}
        onRetry={() => query.refetch()}
        isEmpty={!hasData}
        emptyText="暂无指数分时数据"
        errorTitle="指数分时加载失败"
        minHeight={height}
        skeletonRows={6}
      >
        <IntradayChart
          data={items}
          prevClose={referenceClose}
          height={height}
          viewKey={`index:${symbol}`}
        />
      </SectionDataState>

      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontWeight: Number(t.weight.semibold) }}>{name || symbol} 当日分时图（大图模式）</span>
            {displayPrice != null && (
              <span style={{
                fontFamily: "var(--c-font-mono)",
                fontSize: t.font.base,
                fontWeight: Number(t.weight.bold),
                color: changePct == null || changePct === 0 ? c.textPrimary : changePct > 0 ? c.up : c.down,
              }}>
                {displayPrice.toFixed(2)}
              </span>
            )}
            <ChangeValue value={changePct ?? null} showIcon />
          </div>
        }
        open={expanded}
        onCancel={() => setExpanded(false)}
        footer={null}
        width="min(1280px, 94vw)"
        style={{ top: 24 }}
        destroyOnHidden
      >
        <div style={{ padding: "8px 0" }}>
          <IntradayChart
            data={items}
            prevClose={referenceClose}
            height={560}
            viewKey={`index-modal:${symbol}`}
          />
        </div>
      </Modal>
    </Card>
  );
}
