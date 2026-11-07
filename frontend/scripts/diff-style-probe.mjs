// 比对两次探针产物：只比较两轮都存在且两轮内都稳定的属性值。
import fs from "node:fs";
import path from "node:path";

const [dirA, dirB] = process.argv.slice(2);
if (!dirA || !dirB) {
  console.error("用法: node scripts/diff-style-probe.mjs <基线目录> <新目录>");
  process.exit(2);
}

const readAll = (dir) => {
  const map = new Map();
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".json")) continue;
    map.set(f, JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")));
  }
  return map;
};

const a = readAll(dirA);
const b = readAll(dirB);

let scenarios = 0;
let elements = 0;
let values = 0;
const signatures = new Map();
const onlyOneSide = new Map();

// 滚动条是否出现会整体挪动 18px 宽度，并级联影响换行与元素尺寸，是最大的跨运行噪声源
// （同一份代码跑两次即可产生数十处差异）。两边滚动条状态不同时，尺寸类差异基本不可信，
// 必须显式提示重跑，而不是让这些差异冒充回归。
const scrollbarMismatch = [];

for (const [name, da] of a) {
  const db = b.get(name);
  if (!db) {
    onlyOneSide.set(name, "仅基线有");
    continue;
  }
  const ca = da.chrome || {};
  const cb = db.chrome || {};
  if (ca.scrollbarElements !== undefined && cb.scrollbarElements !== undefined) {
    if (Math.abs(ca.scrollbarElements - cb.scrollbarElements) > 0) {
      scrollbarMismatch.push(
        `${name}（含滚动条元素数 ${ca.scrollbarElements} -> ${cb.scrollbarElements}）`,
      );
    }
  }
  let scenarioHit = false;
  const sa = da.styles || {};
  const sb = db.styles || {};
  for (const key of Object.keys(sa)) {
    if (!(key in sb)) continue; // 结构增删属噪声，不计入属性值差异
    const va = sa[key].split("|");
    const vb = sb[key].split("|");
    if (va.length !== vb.length) continue;
    let elementHit = false;
    for (let i = 0; i < va.length; i++) {
      if (va[i] === vb[i]) continue;
      elementHit = true;
      scenarioHit = true;
      values++;
      const sig = `${i}: ${va[i]} -> ${vb[i]}`;
      const entry = signatures.get(sig) || { n: 0, example: key };
      entry.n++;
      signatures.set(sig, entry);
    }
    if (elementHit) elements++;
  }
  if (scenarioHit) scenarios++;
}

console.log(`场景: 基线 ${a.size} / 新 ${b.size}`);
if (scrollbarMismatch.length) {
  console.log("");
  console.log(
    `⚠ 滚动条状态不一致的场景 ${scrollbarMismatch.length} 个 —— 这些场景的尺寸差异基本是噪声，建议重跑：`,
  );
  for (const line of scrollbarMismatch) console.log(`   ${line}`);
  console.log("");
}
console.log(`有差异场景: ${scenarios}，涉及元素: ${elements}，差异属性值: ${values}`);
if (onlyOneSide.size) console.log(`仅一侧存在的场景: ${onlyOneSide.size}`);

const sorted = [...signatures.entries()].sort((x, y) => y[1].n - x[1].n);
for (const [sig, info] of sorted.slice(0, 30)) {
  console.log(`  ${String(info.n).padStart(4)} × ${sig}`);
  if (info.n > 0) {
    const tail = info.example.split(">").slice(-3).join(">");
    console.log(`         例: ${tail}`);
  }
}
if (!sorted.length) console.log("✅ 两轮计算样式完全一致");
