import fs from "node:fs";
import path from "node:path";

const dir = process.argv[2] || "/tmp/density";
const files = fs.readdirSync(dir).filter((f) => f.endsWith(".json"));
const dumps = files.map((f) => ({ file: f, ...JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) }));

const deskDumps = dumps.filter((d) => (d.size?.width ?? 0) >= 1024);
const mobDumps = dumps.filter((d) => (d.size?.width ?? 0) < 1024);
const sumOf = (list, key) => list.reduce((a, d) => a + (d[key] || 0), 0);
const mergeOf = (list, key) => {
  const total = {};
  for (const d of list) for (const [k, v] of Object.entries(d[key] || {})) total[k] = (total[k] || 0) + v;
  return Object.entries(total).sort((a, b) => b[1] - a[1]);
};
const pct = (entries, n = 5) => {
  const s = entries.reduce((a, [, v]) => a + v, 0) || 1;
  return entries.slice(0, n).map(([k, v]) => `${k} ×${v} (${((v / s) * 100).toFixed(0)}%)`);
};
const median = (arr) => {
  if (!arr.length) return null;
  const s = [...arr].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
};
const routeOf = (u) => (u || "").replace(/^https?:\/\/[^/]+/, "");

console.log(`场景数 ${dumps.length}（桌面 ${deskDumps.length} / 移动 ${mobDumps.length}）`);
for (const [label, list] of [["桌面", deskDumps], ["移动", mobDumps]]) {
  console.log(
    `${label}: 卡片 ${sumOf(list, "cardCount")}（small ${sumOf(list, "cardSmallCount")}） · 表格 ${sumOf(list, "tableCount")}` +
      `（small ${list.reduce((a, d) => a + (d.tableSizes?.small || 0), 0)} / medium ${list.reduce((a, d) => a + (d.tableSizes?.medium || 0), 0)} / 默认 ${list.reduce((a, d) => a + (d.tableSizes?.default || 0), 0)}）`,
  );
}

const METRICS = [
  ["卡片 body padding（small 卡）", "cardBodyPaddingSmall"],
  ["卡片 body padding（默认卡）", "cardBodyPaddingDefault"],
  ["表格 cell padding（small 表）", "tableCellPaddingSmall"],
  ["表格 cell padding（medium 表）", "tableCellPaddingMedium"],
  ["表格 cell padding（默认表）", "tableCellPaddingDefault"],
  ["表单 item margin-bottom", "formItemMarginBottom"],
  ["Descriptions cell padding", "descCellPadding"],
  ["Tabs nav margin-bottom", "tabsNavMarginBottom"],
  ["按钮 height", "buttonHeights"],
  ["输入框 padding", "inputPadding"],
  ["Space gap", "sectionGaps"],
];

for (const [label, list] of [["桌面", deskDumps], ["移动", mobDumps]]) {
  console.log(`\n######## ${label} 间距分布 ########`);
  for (const [l, key] of METRICS) {
    const e = mergeOf(list, key);
    if (!e.length) continue;
    console.log(`${l}: ${pct(e).join(" | ")}`);
  }
}

const desk = deskDumps
  .map((d) => {
    const top = (k) => Object.entries(d[k] || {}).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "-";
    return {
      w: d.size.width,
      h: d.scrollHeight,
      url: routeOf(d.url),
      cards: d.cardCount,
      small: d.cardSmallCount,
      cardPad: top("cardBodyPaddingDefault"),
      tables: d.tableCount,
      smallT: d.tableSizes?.small ?? 0,
      midT: d.tableSizes?.medium ?? 0,
      cellPad: top("tableCellPadding"),
      formM: top("formItemMarginBottom"),
      tabsM: top("tabsNavMarginBottom"),
      rowH: median(d.tableRowHeights || []),
    };
  })
  .sort((a, b) => b.h - a.h);

console.log("\n== 桌面场景高度 Top 18 ==");
console.log(["高", "宽", "路由", "卡片(小)", "默认卡padding", "表格(小/中)", "单元格padding", "表单mb", "Tabs mb", "行高中位"].join("\t"));
for (const r of desk.slice(0, 18)) {
  console.log([r.h, r.w, r.url, `${r.cards}(${r.small})`, r.cardPad, `${r.tables}(${r.smallT}/${r.midT})`, r.cellPad, r.formM, r.tabsM, r.rowH].join("\t"));
}

const housing = [...new Set(desk.filter((r) => r.cardPad === "24px 24px 24px 24px").map((r) => r.url))];
console.log(`\n== 仍用默认 24px 卡片内边距的桌面路由（${housing.length}）==`);
for (const u of housing) console.log(`- ${u}`);
