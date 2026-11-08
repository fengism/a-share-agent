// 计算样式差分探针的采样实现（由 e2e/base.ts 统一挂载）。
// 只在 PROBE_OUT 存在时才工作，否则不产生任何开销。
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";

export const PROBE_PROPS = [
  "display",
  "position",
  "flexDirection",
  "flexWrap",
  "justifyContent",
  "alignItems",
  "gap",
  "gridTemplateColumns",
  "gridTemplateRows",
  "gridAutoFlow",
  "width",
  "height",
  "minWidth",
  "maxWidth",
  "minHeight",
  "maxHeight",
  "marginTop",
  "marginRight",
  "marginBottom",
  "marginLeft",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  "borderTopWidth",
  "borderTopStyle",
  "borderTopColor",
  "borderRadius",
  "background",
  "backgroundColor",
  "boxShadow",
  "color",
  "fontSize",
  "fontWeight",
  "fontFamily",
  "lineHeight",
  "letterSpacing",
  "textAlign",
  "textTransform",
  "overflowX",
  "overflowY",
  "opacity",
  "transform",
  "zIndex",
  "visibility",
  "boxSizing",
  "flexGrow",
  "flexShrink",
  "flexBasis",
];

const SKIP_SELECTOR =
  ".ant-wave, .ant-message, .ant-notification, .ant-dropdown, .ant-select-dropdown, .ant-tooltip, .ant-popover";

export async function recordProbe(page: Page, title: string): Promise<void> {
  const outDir = process.env.PROBE_OUT;
  if (!outDir) return;
  const file = path.join(outDir, `${title}.json`);

  try {
    await page.addStyleTag({
      content: "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}",
    });
    await page.waitForTimeout(800);

    const sample = () =>
      page.evaluate(
        ([props, skip]) => {
          const skipSel = skip as string;
          const propList = props as string[];
          const keyOf = (tag: string, classes: string[]) =>
            `${tag}${classes
              .filter((c) => c && !/^css-[a-z0-9]+$/i.test(c))
              .map((c) => "." + c)
              .join("")}`;

          const out: Record<string, string> = {};
          const roots = Array.from(document.body.children);
          const walk = (el: Element, prefix: string) => {
            if (el.closest(skipSel)) return;
            const parent = el.parentElement;
            let idx = 0;
            if (parent) {
              const sameTag = Array.from(parent.children).filter((c) => c.tagName === el.tagName);
              idx = sameTag.indexOf(el);
            }
            const seg = `${keyOf(el.tagName.toLowerCase(), Array.from(el.classList))}[${idx}]`;
            const key = prefix ? `${prefix}>${seg}` : seg;
            const cs = getComputedStyle(el);
            // getPropertyValue 只认 kebab 写法（font-size），若直接传驼峰 fontSize 会静默返回空串。
            out[key] = propList
              .map((p) => String(cs.getPropertyValue(p.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`))))
              .join("|");
            for (const child of Array.from(el.children)) walk(child, key);
          };
          for (const r of roots) walk(r, "");
          return out;
        },
        [PROBE_PROPS, SKIP_SELECTOR],
      );

    const first = await sample();
    await page.waitForTimeout(400);
    const second = await sample();

    const stable: Record<string, string> = {};
    let dropped = 0;
    for (const key of Object.keys(first)) {
      if (second[key] !== undefined && first[key] === second[key]) stable[key] = first[key];
      else dropped++;
    }

    // 滚动条是否出现会整体挪动 18px 宽度并级联影响换行，是最大的跨运行噪声源。
    // 注意：document 级指标在 headless 下恒为 0（收缩发生在内部滚动容器上），
    // 所以这里统计「所有含滚动条的元素个数」作为全局信号。
    const chrome = await page.evaluate(() => {
      let scrollbarElements = 0;
      for (const el of Array.from(document.querySelectorAll("*"))) {
        if (el instanceof HTMLElement && el.offsetWidth - el.clientWidth > 1) scrollbarElements++;
      }
      return {
        scrollbarElements,
        docScrollbar: window.innerWidth - document.documentElement.clientWidth,
        scrollHeight: document.documentElement.scrollHeight,
      };
    });

    mkdirSync(outDir, { recursive: true });
    writeFileSync(
      file,
      JSON.stringify({
        url: page.url(),
        size: page.viewportSize(),
        unstable: dropped,
        chrome,
        styles: stable,
      }),
    );
  } catch {
    // 探针失败不应影响 e2e 结论
  }
}
