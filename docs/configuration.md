# 配置系统开发指南

本文说明平台配置的存储位置、字段作用域，以及**新增/修改配置项的标准流程**。
目标是让配置只有一处声明，避免 `.env` / 数据库 / 配置 API / 前端之间再次漂移。

---

## 一、配置从哪里来

```
.env / 环境变量  ─┐
                  ├─►  Settings（pydantic-settings）  ──►  运行时读取
global_config 表 ─┤        ▲
user_config 表   ─┘        │
                           └──  配置 API（PUT /api/config）
```

- **`Settings`**：应用启动时的基线配置，来源为 `.env`、环境变量与数据库中的持久化全局项。
- **生效配置**：`get_effective_settings()` 在请求上下文中把当前用户的私有覆盖叠加到基线上；
  后台任务无用户上下文，只能读到全局基线。
- **配置 API**：`GET/PUT /api/config` 读写用户私有项与管理员全局项，敏感字段下发时脱敏。

## 二、唯一事实来源

**`backend/app/configuration/api_models.py` 是配置接口契约的唯一声明处。**

- `ConfigUpdateRequest`：接口可编辑字段全集，每个字段用 `Annotated[..., ConfigMeta]` 标注：
  - `scope`：`private`（每个用户可覆盖，落 `user_config`）或 `global`（仅管理员，落 `global_config`）；
  - `secret`：入库加密、接口下发脱敏；
  - `synced_global`：private 字段中，管理员保存时额外同步到全局基线，供后台任务复用；
  - `group`：领域分组。
- 以下全部由它**自动派生**，无需手工维护：
  - `PRIVATE_USER_KEYS` / `PERSISTED_GLOBAL_KEYS` / `SECRET_KEYS` / `GLOBAL_SYNCED_KEYS`
  - `ConfigResponse`（只读响应模型）
  - `CONFIG_FIELD_GROUPS`

> ⚠️ 不要再手写配置键清单。历史上 `PRIVATE_USER_KEYS` 等多份清单曾导致
> 推送通道、fuyao 凭证等字段「界面能填、后端静默丢弃」。

## 三、字段作用域速查

| 作用域 | 存储 | 谁能改 | 例子 |
| :--- | :--- | :--- | :--- |
| `private` | `user_config` | 任意登录用户 | 大模型 Key、问财 Key、飞书私有空间 |
| `private` + `synced_global` | `user_config` + `global_config` | 任意用户；管理员保存时同步全局 | 大模型、推送通道、飞书应用凭证 |
| `global` | `global_config` | 仅管理员 | 数据源 Cookie、出站代理、备份策略 |
| 非 API（deployment-only） | 仅 `.env` / 环境变量 | 部署者 | `PDF_MAX_CONCURRENCY`、`WORKFLOW_JOB_*` |

## 四、新增一个配置项（标准流程）

1. **后端字段**：在 `app/configuration/groups/<领域>.py` 对应分组类里加字段
   （扁平名，如 `llm_xxx`）；分组类通过多继承组合进 `Settings`。
2. **接口契约**：在 `api_models.py` 的 `ConfigUpdateRequest` 里加同名字段，
   并用 `ConfigMeta` 标注 `scope` / `group`（必要时 `secret` / `synced_global`）。
   - 不需要暴露给接口的部署项**不要**加到这里。
3. **`.env.example`**：补一行带注释的示例键。
4. **前端**：在 `frontend/src/pages/Settings/cardSpecs.ts` 把字段加入对应卡片；
   `ConfigData` 类型会自动从 OpenAPI 生成类型获得该字段，无需手写。
   若该字段刻意不提供界面，请加入 `cardSpecs.test.ts` 的 `NO_UI_FIELDS` 并注明原因。
5. **OpenAPI**：在 `frontend/` 下执行 `npm run api:generate`，提交生成产物。
6. **运行测试**：见下方「五、一致性守卫」。

## 五、一致性守卫

以下测试会在 CI 中拦截漂移：

| 测试 | 作用 |
| :--- | :--- |
| `tests/test_config_consistency.py` | API 字段 ↔ `Settings` ↔ `.env.example` 三方一致；作用域划分互斥且完整；`.env.example` 无无效键、默认值一致 |
| `tests/test_push_config_api.py` | 推送通道与 fuyao 凭证可经接口读写；管理员同步全局；未知字段被拒 |
| `tests/test_feishu_credential_merge.py` | 飞书凭证合并的向后兼容（旧 `BOT_FEISHU_APP_*` 回退） |
| `frontend .../cardSpecs.test.ts` | 卡片声明与保存/撤销/脏检查派生逻辑；并校验**每个后端可编辑字段都被某张卡片覆盖**，否则必须登记到 `NO_UI_FIELDS` |

`api_models.py` 在导入时即校验字段与元数据完整，缺元数据会直接抛错。

## 六、向后兼容规则（线上必须遵守）

- **环境变量名不可改**：旧名要么保留，要么提供回退别名（如 `BOT_FEISHU_APP_ID` → `FEISHU_APP_ID`）。
- **数据库键不可静默废弃**：移除键前需迁移或保留只读回退。
- **配置 API 只增不删**：删除字段会让旧前端保存失败；先标记弃用，下一个大版本再移除。
- **`.env.example` 与 schema 默认值不一致时**，必须加入
  `test_config_consistency.py::INTENTIONAL_DEFAULT_OVERRIDES` 并注明原因。

## 七、Settings 分组与嵌套访问

`Settings` 由 `app/configuration/groups/` 下的分组类多继承组合而成，
字段仍是**扁平访问**（`settings.llm_provider`），同时提供嵌套视图：

```python
settings.llm.provider            # == settings.llm_provider
settings.push.feishu_webhook_url
settings.llm.provider = "openai" # 写回同一份状态
```

分组类与嵌套视图只是组织方式，不引入第二份数据；`.env` / 数据库 / 接口契约均不受影响。

## 八、相关文档

- 推送与通知通道：[push-notifications.md](push-notifications.md)
- 部署与环境变量：仓库根目录 `README.md`
