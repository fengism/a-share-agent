export function parseCompareCodes(value: string): string[] {
  return Array.from(new Set(
    value
      .split(",")
      .map((code) => code.trim())
      .filter((code) => /^\d{6}$/.test(code)),
  )).slice(0, 5);
}

export function serializeCompareCodes(codes: string[]): string {
  return parseCompareCodes(codes.join(",")).join(",");
}
