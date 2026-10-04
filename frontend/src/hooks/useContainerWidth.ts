import { useCallback, useEffect, useRef, useState } from "react";

/**
 * 观测元素内容宽度。用于"容器查询"场景——组件按**容器**宽度而非视口宽度切换布局。
 *
 * 为什么需要：首页侧栏卡片在 1600px 视口下也只有 ~400px 宽，用视口断点
 * (`max-width: 768px`) 判断会误判成宽屏，把 635px 的表格塞进 406px 的容器，
 * 右侧列被 `overflow: hidden` 裁掉且没有可见滚动条。
 *
 * @returns `[ref, width]`：把 `ref` 挂到目标容器，`width` 为内容宽度（px，未挂载时为 0）
 */
export function useContainerWidth<T extends HTMLElement = HTMLDivElement>(): [
  (node: T | null) => void,
  number,
] {
  const [width, setWidth] = useState(0);
  const observerRef = useRef<ResizeObserver | null>(null);
  const nodeRef = useRef<T | null>(null);

  const measure = useCallback(() => {
    const node = nodeRef.current;
    if (!node) return;
    const next = node.clientWidth;
    setWidth((prev) => (prev === next ? prev : next));
  }, []);

  const ref = useCallback(
    (node: T | null) => {
      observerRef.current?.disconnect();
      observerRef.current = null;
      nodeRef.current = node;
      if (!node) {
        setWidth(0);
        return;
      }
      measure();
      if (typeof ResizeObserver === "undefined") return;
      const observer = new ResizeObserver(measure);
      observer.observe(node);
      observerRef.current = observer;
    },
    [measure],
  );

  useEffect(() => () => observerRef.current?.disconnect(), []);

  return [ref, width];
}