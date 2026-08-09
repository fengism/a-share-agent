export function shouldFitChartContent(previousViewKey: string | null, nextViewKey: string): boolean {
  return previousViewKey === null || previousViewKey !== nextViewKey;
}
