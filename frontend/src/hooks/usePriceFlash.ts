import { useEffect, useRef, useState } from "react";

export type PriceFlashType = "tick-flash-up" | "tick-flash-down" | "";

/**
 * 监测价格实时变动并在发生跳价时触发微弱呼吸高亮（持续指定时长）。
 *
 * @param price 当前最新价
 * @param durationMs 闪烁持续时间（默认 600ms）
 * @returns 对应的 CSS 类名：'tick-flash-up' | 'tick-flash-down' | ''
 */
export function usePriceFlash(
  price: number | null | undefined,
  durationMs = 600,
): PriceFlashType {
  const [flashClass, setFlashClass] = useState<PriceFlashType>("");
  const prevPriceRef = useRef<number | null | undefined>(price);

  useEffect(() => {
    const prev = prevPriceRef.current;
    prevPriceRef.current = price;

    if (
      prev != null &&
      price != null &&
      Number.isFinite(prev) &&
      Number.isFinite(price) &&
      prev !== price
    ) {
      const cls: PriceFlashType = price > prev ? "tick-flash-up" : "tick-flash-down";
      setFlashClass(cls);

      const timer = window.setTimeout(() => {
        setFlashClass("");
      }, durationMs);

      return () => {
        window.clearTimeout(timer);
      };
    }
  }, [price, durationMs]);

  return flashClass;
}
