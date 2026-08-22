import dayjs from "dayjs";

export function oneYearAgoDate() {
  return dayjs().subtract(1, "year").format("YYYYMMDD");
}

export function normalizeIsoDate(value: string, fallback: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return fallback;
  const parsed = dayjs(value);
  return parsed.isValid() && parsed.format("YYYY-MM-DD") === value ? value : fallback;
}
