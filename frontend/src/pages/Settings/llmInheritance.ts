/** 「改用管理员配置」提交的补丁：显式清空个人 LLM 端点与凭据覆盖。
 *
 * 必须显式传空串而不是省略字段：
 * - 端点字段（provider/base_url/model/...）清空后 overlay 会跳过，从而继承全局值；
 * - `llm_api_key` 是密钥字段，后端把"显式空串"解释为删除个人覆盖 —— 若只是省略，
 *   用户此前存下的个人 Key 会继续生效，按钮的承诺就不成立。
 */
import type { ConfigUpdate } from "../../types/settings";

export const PERSONAL_LLM_FIELDS = [
  "llm_provider",
  "llm_base_url",
  "llm_model",
  "llm_api_key",
  "llm_api_mode",
  "llm_api_version",
  "llm_sub_model",
  "llm_simple_tasks",
] as const;

export const PERSONAL_LLM_CLEAR_PATCH: ConfigUpdate = {
  ...(Object.fromEntries(PERSONAL_LLM_FIELDS.map((key) => [key, ""])) as ConfigUpdate),
  // `llm_api_mode` 在接口契约里是 Literal["auto","openai","litellm"]，空串会被 422 拒绝，
  // 因此显式写回文档语义的 `auto`（跟随 Provider）作为"回到默认"的表达。
  llm_api_mode: "auto",
};
