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

### 私密字段的继承规则（以 LLM 为例）

普通用户不需要配 Key：没有个人覆盖的字段一律继承管理员写入的全局基线。
界面上只有状态标签（`沿用管理员配置` / `个人端点`）与一句提示，
端点类字段（Base URL / API 模式 / 子模型 / 上下文长度）收在「端点与模型」折叠区，默认不展开。

| 用户操作 | 生效结果 |
| :--- | :--- |
| 什么都不配 | 完全使用管理员配置（Provider / Base URL / Model / Key） |
| 不改 URL 和 Key，单独修改模型或温度 | 自由修改模型与温度，端点与 Key 依然安全继承管理员配置 |
| 自定义端点（同时提供 Base URL 与 Key） | 使用完整的个人自建端点与私有凭据 |
| 只填 Key 不改 URL / 只改 URL 不填 Key | **前端与后端双重拦截**：自定义端点需同时配置 Base URL 与 API Key |
| 清空个人配置并保存（界面上的「改用管理员配置」） | 删除个人覆盖，全量回退到管理员配置 |

> [!NOTE]
> **未改动的字段不会提交**：LLM 卡片声明了 `skipUnchanged`（`cardSpecs.ts`），保存时只提交与当前生效值
> 不同的字段。否则表单用生效值初始化后，用户仅仅改了温度再保存，就会把管理员的 Provider / Base URL /
> Model 静默写成自己的覆盖，之后管理员调整全局配置这个人再也跟不上。

实现见 `app/configuration/effective.py::overlay_private`：只有端点（`llm_base_url` + `llm_provider`）
与全局一致时才复用全局 Key，同一规则此前已用于问财自定义地址。`GET /api/config` 的
`inherited_keys` 会列出仍继承全局的字段，前端据此显示「当前使用管理员配置」并提供「改用管理员配置」。

#### 子模型与备用模型

`LLM_SUB_MODEL`（简单/高频任务）与 `LLM_FALLBACK_MODEL`（自动降级兜底）都**与主模型共用
provider / base_url / api_key，只替换 `model`**。由此得到两条硬约束：

1. 必须填同一家厂商的模型名，否则请求必然 404/400；
2. 切换 Provider 时二者会被一并重置（用户在同一次提交里显式给出时除外），否则残留的旧厂商
   模型名会变成一条"永远失败的兜底路径"。

降级触发条件（`app/infrastructure/llm/completion.py`）：
| 上游错误 | 是否降级 | 理由 |
| :--- | :--- | :--- |
| 429 / 402（限流、额度/余额耗尽） | 立即降级 | 账号级问题，换模型可能立即恢复 |
| 5xx | 重试预算耗尽后降级 | 主模型路由当前不可用 |
| 400 / 401 / 403 / 404 / 422 | **不降级** | 请求或凭证本身有误，换模型只会掩盖真实原因 |
| 超时 / 取消 | **不降级** | 备用模型可能更慢，且上层已有总时限预算 |

**子模型回退主模型**（`LLM_SUB_MODEL` 走不通时）共享同一套降级判据，但多两条约束：

- 子模型已经把生成总时限（`LLM_GENERATION_TIMEOUT_SECONDS`，默认 1200s）用完时，**不再回退主模型**。
  超时是确定性失败，重试只是白等。
- 子模型与主模型**共用同一份生成总预算**：主模型只能拿到剩余时间；剩余不足 1s 时直接透出子模型的
  真实错误，不再发起注定立刻超时的请求。

额度判定只认 HTTP 状态码与明确的限流措辞，**不做裸 `429` 子串匹配**——上游 400 消息里出现
`max_tokens 14290 exceeds` 这类数字很常见。

降级时会为备用模型**从同一个连接池租一个客户端**（池键含 `model`，因此不会与主客户端抢同一条目），
能力位与请求整形也按新模型重算——直接改 `model` 字段会让 SDK 封装层的 `expected_model` 校验
报 `LLMConfigurationError`。池化而不是每次新建，是因为 429 恰恰成批出现、系统已经吃紧的时候，
反复重做 DNS/TCP/TLS 握手只会雪上加霜。

降级是**尽力而为**：只有请求能装进备用模型时才真的切换。若备用模型缺主模型支持的能力（例如工具调用），
重新整形会失败，此时**放弃降级并保留原始错误**（同时记 `fallback_incompatible` 指标），
而不是把手里的 429 偷换成“当前模型网关未启用工具调用能力”。

#### 降级的可观测性

降级链路的计数都带 `operation` 维度，并通过 Prometheus 导出为
`a_share_provider_operation_{attempts,successes,failures,fallback_attempts}_total{provider,operation}`：

| `operation` | 含义 |
| --- | --- |
| `completion` / `stream` | 常规调用 |
| `fallback_to_model` | 成功切换到备用模型 |
| `fallback_unavailable` | 备用模型客户端构建失败，放弃降级 |
| `fallback_incompatible` | 备用模型装不下请求（如缺工具调用），放弃降级 |
| `tools_unsupported` | 模型不支持工具调用，降级重试 |

`fallback_attempts` 在三类 `fallback_*` 上都会 +1，聚合的 `a_share_provider_fallback_attempts_total`
因此等于「所有想降级的次数」，可直接拿来做告警：

```promql
# 备用模型配置有问题（构建失败或装不下请求），需要人工介入
sum by (operation) (increase(a_share_provider_operation_failures_total{operation=~"fallback_unavailable|fallback_incompatible"}[1h])) > 0
```

> [!IMPORTANT]
> **私密字段的"空串"是删除指令**：`PUT /api/config` 里某个私密字段传空串，表示删除该用户的个人覆盖
> （`user_config` 直接删行），而不是写入空值。它与 `overlay_private` 跳过空值的结果等价，但不留死数据。
> 否则前端"改用管理员配置"会因为 `buildCardPatch` 跳过空密钥而删不掉旧 Key。掩码值（含 `***`）依然视为
> "未修改"，不会误删。`llm_api_mode` 是 `Literal` 契约、不接受空串，清空时按文档语义写回 `auto`（跟随 Provider）。

> [!CAUTION]
> 换端点必须自备 Key。这条规则在**两个层次**同时生效，任何一层都能独立挡住凭据外泄：
> 1. 语义层 `overlay_private`：端点和全局不一致时，不把全局 Key 填进用户生效配置；
> 2. 咽喉层 `resolve_llm_client_spec`（把配置变成实际出网请求的唯一位置）：Key 为空时，只有端点与全局
>    一致才回退复用全局 Key，否则报错 `LLM_API_ERROR / config.llm_credentials_missing`（HTTP 422），
>    提示用户填自己的 Key。本地无需 Key 的 provider（如 Ollama）不受影响。

## 三、字段作用域速查

| 作用域 | 存储 | 谁能改 | 例子 |
| :--- | :--- | :--- | :--- |
| `private` | `user_config` | 任意登录用户 | 大模型 Key、问财 Key、飞书私有空间 |
| `private` + `synced_global` | `user_config` + `global_config` | 任意用户；管理员保存时同步全局 | 大模型、推送通道、飞书应用凭证 |
| `global` | `global_config` | 仅管理员 | 数据源 Cookie、出站代理、备份策略 |
| 非 API（deployment-only） | 仅 `.env` / 环境变量 | 部署者 | `PDF_MAX_CONCURRENCY`、`WORKFLOW_JOB_*`、`*_AUDIT_RETENTION_DAYS` |

> [!NOTE]
> 两类审计表的清理期限是部署项（不可从界面改）：`LOGIN_AUDIT_RETENTION_DAYS`（默认 180 天）
> 与 `ADMIN_AUDIT_RETENTION_DAYS`（默认 365 天），`0` 表示永久保留。它们由 6 小时一次的
> 维护任务执行，与 `auth_sessions` / `password_resets` 的清理同批。

> [!IMPORTANT]
> `ADMIN_SETUP_TOKEN`（默认空）用于锁住**空库首用户注册**：不配时第一个注册者直接成为管理员，
> 只适合「部署后立刻注册」。若实例在注册前即可被公网访问，请配一个随机口令——注册页面会
> 多出一个「部署口令」输入框，口令错误返回 403 `auth.setup_token_invalid`。
> 用户表非空后该口令不再参与任何校验。

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

- 部署、常用配置与常见问题：[README](../README.md)
- 本地开发、质量门禁与测试约定：[development.md](development.md)
- 分层与依赖规则：[architecture.md](architecture.md)
- 数据源与降级机制：[data-sources.md](data-sources.md)
- 故障排查：[troubleshooting.md](troubleshooting.md)
- 推送与通知通道：[push-notifications.md](push-notifications.md)
