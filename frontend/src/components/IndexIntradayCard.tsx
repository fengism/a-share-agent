import { Card, Typography } from "antd";
import { useMarketIndexIntraday } from "../api/queries";
import IntradayChart from "../charts/IntradayChart";
import ChangeValue from "./ChangeValue";
import SectionDataState from "./SectionDataState";
import { useColors, useTokens } from "../styles/ui";
import { deriveIndexPrevClose } from "../utils/indexIntraday";
import "./index-intraday-card.css";

const { Text } = Typography;

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
  height = 360,
}: Props) {
  const c = useColors();
  const t = useTokens();
  const query = useMarketIndexIntraday(symbol);
  const items = query.data?.items ?? [];
  const hasData = items.length > 0;
  const latestItem = items.length > 0 ? items[items.length - 1] : undefined;
  const displayPrice = latestItem?.price ?? price;
  const latestMinute = latestItem?.time?.slice(0, 5);
  const referenceClose = query.data?.prev_close
    ?? preClose
    ?? deriveIndexPrevClose(price, changePct);

  return (
    <Card
      size="small"
      className="index-intraday-card"
      title={<span style={{ fontWeight: Number(t.weight.semibold) }}>{name || symbol} 分时</span>}
      extra={<Text type="secondary">{query.data?.source === "sina_direct" ? "新浪财经" : "实时分钟线"}</Text>}
      style={{ borderRadius: t.radius.md, border: `1px solid ${c.border}`, boxShadow: t.shadow.xs }}
    >
      <div className="index-intraday-summary">
        <div className="index-intraday-summary__quote">
          <strong>{displayPrice?.toFixed(2) ?? "-"}</strong>
          <ChangeValue value={changePct ?? null} />
          <span>{latestMinute ? `更新 ${latestMinute}` : "等待分钟数据"}</span>
        </div>
        <div className="index-intraday-summary__legend" aria-label="分时图图例">
          <span className="is-price">价格</span>
          <span className="is-average">均价</span>
          <span className="is-volume">成交量</span>
        </div>
      </div>
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
    </Card>
  );
}
