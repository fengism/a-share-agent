import dayjs from "dayjs";

const moneyFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const priceFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

const integerFormatter = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 0,
});

export function formatMoney(value: number | null | undefined) {
  return value == null ? "-" : `¥${moneyFormatter.format(value)}`;
}

export function formatPrice(value: number | null | undefined) {
  return value == null ? "-" : `¥${priceFormatter.format(value)}`;
}

export function formatInteger(value: number) {
  return integerFormatter.format(value);
}

export function formatTime(value: string) {
  const parsed = dayjs(value);
  return parsed.isValid() ? parsed.format("YYYY-MM-DD HH:mm") : value;
}

export function errorMessage(error: unknown) {
  return error instanceof Error && error.message ? error.message : "操作失败，请稍后重试";
}
