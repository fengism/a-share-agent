export function deriveIndexPrevClose(
  price: number | null | undefined,
  changePct: number | null | undefined,
): number | null {
  if (price == null || changePct == null) return null;
  const ratio = 1 + changePct / 100;
  return price > 0 && ratio > 0 ? price / ratio : null;
}
