import { describe, expect, it } from "vitest";
import openapiRaw from "../../api/generated/openapi.json?raw";
import type { ConfigData, ConfigUpdate } from "../../types/settings";
import {
  CARD_KEYS,
  CARD_SPECS,
  buildCardPatch,
  buildCardReset,
  isCardDirty,
  isMaskedValue,
} from "./cardSpecs";

/** 可经配置接口读写、但不在「设置」页提供输入框的字段（必须显式登记）。 */
const NO_UI_FIELDS = new Set<string>([
  // 部署期通过 .env 配置的网络开关
  "http_trust_env",
  // 已弃用：Bot 复用 feishu_app_*，保留仅为兼容旧部署
  "bot_feishu_app_id",
  "bot_feishu_app_secret",
  // 由「能力中心」页面管理，不重复出现在设置页
  "disabled_chat_skills",
  "disabled_chat_agents",
]);

function apiEditableFields(): string[] {
  const spec = JSON.parse(openapiRaw) as {
    components: { schemas: { ConfigUpdateRequest: { properties: Record<string, unknown> } } };
  };
  return Object.keys(spec.components.schemas.ConfigUpdateRequest.properties);
}

function asConfig(values: Partial<ConfigData>): ConfigData {
  return values as ConfigData;
}

describe("cardSpecs", () => {
  it("每张卡片都有非空字段声明", () => {
    expect(CARD_KEYS.length).toBeGreaterThan(10);
    for (const key of CARD_KEYS) {
      const spec = CARD_SPECS[key];
      const secrets = "secrets" in spec ? spec.secrets.length : 0;
      expect(spec.fields.length + secrets).toBeGreaterThan(0);
    }
  });

  it("buildCardPatch 原样提交普通字段、跳过掩码与空密钥", () => {
    const form: ConfigUpdate = {
      push_auto_enabled: true,
      feishu_webhook_url: "https://example.invalid/hook",
      feishu_webhook_secret: "new-secret",
      dingtalk_webhook_secret: "SEC***mask",
      wxpusher_app_token: "",
    };
    const patch = buildCardPatch(form, CARD_SPECS.notificationChannels);
    expect(patch.push_auto_enabled).toBe(true);
    expect(patch.feishu_webhook_url).toBe("https://example.invalid/hook");
    expect(patch.feishu_webhook_secret).toBe("new-secret");
    expect(patch).not.toHaveProperty("dingtalk_webhook_secret");
    expect(patch).not.toHaveProperty("wxpusher_app_token");
  });

  it("isCardDirty 忽略掩码密钥、识别新值与字段改动", () => {
    const config = asConfig({
      push_auto_enabled: false,
      feishu_webhook_url: "",
      feishu_webhook_secret: "abcd***wxyz",
    });
    const spec = CARD_SPECS.notificationChannels;

    expect(isCardDirty({}, config, spec)).toBe(false);
    // 回填的掩码值不算改动
    expect(isCardDirty({ feishu_webhook_secret: "abcd***wxyz" }, config, spec)).toBe(false);
    // 输入新密钥算改动
    expect(isCardDirty({ feishu_webhook_secret: "fresh" }, config, spec)).toBe(true);
    // 普通字段改动算改动
    expect(isCardDirty({ push_auto_enabled: true }, config, spec)).toBe(true);
  });

  it("buildCardReset 回填生效值（含掩码密钥）", () => {
    const config = asConfig({
      push_auto_enabled: true,
      feishu_webhook_url: "https://example.invalid/hook",
      feishu_webhook_secret: "abcd***wxyz",
    });
    const reset = buildCardReset(config, CARD_SPECS.notificationChannels);
    expect(reset.push_auto_enabled).toBe(true);
    expect(reset.feishu_webhook_url).toBe("https://example.invalid/hook");
    expect(reset.feishu_webhook_secret).toBe("abcd***wxyz");
  });

  it("每张卡片字段都在后端契约内，且后端可编辑字段都有归属", () => {
    const apiFields = new Set(apiEditableFields());
    const declared = Object.values(CARD_SPECS).flatMap((spec) => [
      ...spec.fields,
      ...("secrets" in spec ? spec.secrets : []),
    ]);
    const declaredSet = new Set<string>(declared);

    // 前端不得声明后端不存在的字段（拼写错误/已删除字段）
    const unknown = declared.filter((key) => !apiFields.has(key));
    expect(unknown, `前端声明了后端不存在的字段: ${unknown.join(", ")}`).toEqual([]);

    // 后端可编辑字段必须被某张卡片覆盖，或显式登记为「无 UI」
    const missing = [...apiFields].filter(
      (key) => !declaredSet.has(key) && !NO_UI_FIELDS.has(key),
    );
    expect(
      missing,
      `以下可编辑字段缺少前端入口且未登记到 NO_UI_FIELDS: ${missing.join(", ")}`,
    ).toEqual([]);

    // 同一个字段不得被多张卡片重复声明（避免保存/脏检查口径不一致）
    const duplicates = declared.filter((key, index) => declared.indexOf(key) !== index);
    expect(duplicates, `字段被多张卡片重复声明: ${duplicates.join(", ")}`).toEqual([]);
  });

  it("isMaskedValue 仅识别含 *** 的字符串", () => {
    expect(isMaskedValue("abcd***wxyz")).toBe(true);
    expect(isMaskedValue("plain")).toBe(false);
    expect(isMaskedValue(undefined)).toBe(false);
    expect(isMaskedValue(42)).toBe(false);
  });
});
