export const IMPORT_PLACEHOLDER = `slug: my-chain
name: 我的产业链
category: 新材料
summary: 一句话描述这条产业链。
tags: [新材料]
drivers:
  - 驱动因素一
layers:
  - key: upstream          # upstream / midstream / downstream
    name: 上游 · 原材料
    segments:
      - name: 某环节
        companies:
          - { name: 某公司, code: "600000", note: 一句话定位 }

# 也支持批量：顶层写 chains: [ ... ]，或直接给数组；JSON 同样可导入`;

export const LAYER_ACCENTS = {
  upstream: "warning",
  midstream: "primary",
  downstream: "success",
} as const;

export const LAYER_COLORS: Record<string, string> = {
  upstream: "#f59e0b",
  midstream: "#3b82f6",
  downstream: "#10b981",
};

export const LAYER_NAMES: Record<string, string> = {
  upstream: "上游",
  midstream: "中游",
  downstream: "下游",
};

