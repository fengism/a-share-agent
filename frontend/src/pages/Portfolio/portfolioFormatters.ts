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

const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: "¥",
  HKD: "HK$",
  USD: "US$",
};

/** 按币种返回金额前缀；未知币种直接显示代码，避免误标成人民币。 */
export function currencySymbol(currency: string | null | undefined) {
  if (!currency) return CURRENCY_SYMBOLS.CNY;
  return CURRENCY_SYMBOLS[currency] ?? `${currency} `;
}

export function formatMoney(value: number | null | undefined, currency: string | null | undefined = "CNY") {
  return value == null ? "-" : `${currencySymbol(currency)}${moneyFormatter.format(value)}`;
}

export function formatPrice(value: number | null | undefined, currency: string | null | undefined = "CNY") {
  return value == null ? "-" : `${currencySymbol(currency)}${priceFormatter.format(value)}`;
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
