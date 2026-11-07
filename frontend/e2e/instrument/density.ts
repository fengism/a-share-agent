// 布局密度测量采样实现（由 e2e/base.ts 统一挂载）。
// 只在 DENSITY_OUT 存在时才工作，否则不产生任何开销。
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";

export async function recordDensity(page: Page, title: string): Promise<void> {
  const outDir = process.env.DENSITY_OUT;
  if (!outDir) return;

  try {
    const data = await page.evaluate(() => {
      const buckets = (selector: string, read: (el: Element, cs: CSSStyleDeclaration) => string, cap = 400) => {
        const counts: Record<string, number> = {};
        for (const el of Array.from(document.querySelectorAll(selector)).slice(0, cap)) {
          const v = read(el, getComputedStyle(el));
          counts[v] = (counts[v] || 0) + 1;
        }
        return counts;
      };
      const pad = (el: Element, cs: CSSStyleDeclaration) =>
        [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].join(" ");
      const heights = (selector: string, cap = 400) =>
        Array.from(document.querySelectorAll(selector))
          .slice(0, cap)
          .map((el) => Math.round((el as HTMLElement).getBoundingClientRect().height));

      const tableSizes = { small: 0, medium: 0, default: 0 };
      for (const t of Array.from(document.querySelectorAll(".ant-table"))) {
        if (t.classList.contains("ant-table-small")) tableSizes.small++;
        else if (t.classList.contains("ant-table-medium")) tableSizes.medium++;
        else tableSizes.default++;
      }
      return {
        scrollHeight: document.documentElement.scrollHeight,
        clientHeight: document.documentElement.clientHeight,
        cardCount: document.querySelectorAll(".ant-card").length,
        cardSmallCount: document.querySelectorAll(".ant-card-small").length,
        tableCount: document.querySelectorAll(".ant-table").length,
        tableSizes,
        cardBodyPadding: buckets(".ant-card-body", pad),
        cardBodyPaddingSmall: buckets(".ant-card-small > .ant-card-body", pad),
        cardBodyPaddingDefault: buckets(".ant-card:not(.ant-card-small) > .ant-card-body", pad),
        formItemMarginBottom: buckets(".ant-form-item", (_el, cs) => cs.marginBottom),
        descCellPadding: buckets(".ant-descriptions-item-label, .ant-descriptions-item-content", pad),
        tableCellPadding: buckets(".ant-table-cell", pad),
        tableCellPaddingSmall: buckets(".ant-table-small .ant-table-cell", pad),
        tableCellPaddingMedium: buckets(".ant-table-medium .ant-table-cell", pad),
        tableCellPaddingDefault: buckets(
          ".ant-table:not(.ant-table-small):not(.ant-table-medium) .ant-table-cell",
          pad,
        ),
        tableRowHeights: heights(".ant-table-row"),
        buttonHeights: buckets(".ant-btn", (_el, cs) => cs.height),
        inputPadding: buckets(".ant-input", pad),
        tabsNavMarginBottom: buckets(".ant-tabs-nav", (_el, cs) => cs.marginBottom),
        sectionGaps: buckets(".ant-space", (_el, cs) => cs.gap),
      };
    });

    mkdirSync(outDir, { recursive: true });
    writeFileSync(
      path.join(outDir, `${title}.json`),
      JSON.stringify({ url: page.url(), size: page.viewportSize(), ...data }),
    );
  } catch {
    // 测量失败不应影响 e2e 结论
  }
}
