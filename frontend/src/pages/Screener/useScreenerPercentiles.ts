import { useEffect, useState } from "react";
import { useComputePercentiles } from "../../api/queries";
import type { ScreenerResult } from "../../types/stock";

interface ScreenerPercentileOptions {
  pbPercentileMax: number;
  pePercentileMax: number;
  result: ScreenerResult | undefined;
  showPercentile: boolean;
}

export function useScreenerPercentiles({
  pbPercentileMax,
  pePercentileMax,
  result,
  showPercentile,
}: ScreenerPercentileOptions) {
  const [percentileMap, setPercentileMap] = useState<Map<string, number | null>>(new Map());
  const { mutate: computePercentiles, isPending } = useComputePercentiles();

  useEffect(() => {
    if (!showPercentile || !result?.items.length) {
      setPercentileMap(new Map());
      return;
    }

    const codes = result.items.map((item) => item.code);
    setPercentileMap(new Map());
    computePercentiles(
      { codes, period: "近三年", indicator: "市盈率(TTM)" },
      {
        onSuccess: (percentiles) => {
          const next = new Map<string, number | null>();
          for (const item of percentiles.items) next.set(item.code, item.percentile);
          setPercentileMap(next);
        },
      },
    );
    computePercentiles(
      { codes, period: "近三年", indicator: "市净率" },
      {
        onSuccess: (percentiles) => {
          setPercentileMap((current) => {
            const next = new Map(current);
            for (const item of percentiles.items) next.set(`${item.code}_pb`, item.percentile);
            return next;
          });
        },
      },
    );
  }, [computePercentiles, result?.items, showPercentile]);

  const filteredItems = showPercentile && percentileMap.size > 0
    ? result?.items.filter((item) => {
        const pePercentile = percentileMap.get(item.code);
        const pbPercentile = percentileMap.get(`${item.code}_pb`);
        return (pePercentile == null || pePercentile <= pePercentileMax)
          && (pbPercentile == null || pbPercentile <= pbPercentileMax);
      })
    : result?.items;
  const displayData = filteredItems
    ? { ...result!, items: filteredItems, total: filteredItems.length }
    : result;

  return { displayData, isPending, percentileMap };
}
