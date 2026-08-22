import { queryClient } from "../../api/queryClient";
import { marketIndicesQueryOptions } from "../../api/queryHooks/market";

export async function prefetchMarketOverview(): Promise<void> {
  await queryClient.prefetchQuery(marketIndicesQueryOptions());
}
