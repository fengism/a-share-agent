import { expect, it } from "vitest";
import { readableReferences, reportPresentation } from "./reportPresentation";
import type { IndustryChainResult } from "../../types/stock";

it("replaces legacy inline and Markdown references but preserves link destinations", () => {
  const url = "https://example.com/ev_actual?token=ev_url";
  expect(readableReferences(`证据 ID：\`ev_abc\`；依据ev_def；[官方原文](${url})`)).toBe(`相关资料；依据相关资料；[官方原文](${url})`);
});

it("creates a display copy without changing IDs, citations or stored data", () => {
  const result: IndustryChainResult = { name:"算力", summary:"结论（证据 ev_abc）", upstream:[], midstream:[], downstream:[], key_stocks:[], drivers:[], risks:[], charts:[], llm_review:"ev_abc 原文引用", evidence_catalog:[{evidence_id:"ev_abc",tool_name:"web_fetch",title:"报告",source_urls:["https://example.com/ev_url"]}], relationships:[{title:"关系",source_node:"上游",target_node:"下游",relation_type:"transmission",detail:"依据ev_abc",evidence_ids:["ev_abc"]}] };
  const copy = JSON.stringify(result);
  const display = reportPresentation(result);
  expect(display.summary).toBe("结论（资料 1）");
  expect(display.relationships?.[0].detail).toBe("依据资料 1");
  expect(display.relationships?.[0].evidence_ids).toEqual(["ev_abc"]);
  expect(display.evidence_catalog?.[0].source_urls).toEqual(["https://example.com/ev_url"]);
  expect(JSON.stringify(result)).toBe(copy);
});
