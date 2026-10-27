# 故障排查手册

按"症状 → 先看什么 → 怎么处置"组织。所有命令默认在仓库根目录执行。

## 一、快速定位

```bash
make status                       # 前后端端口是否在听
curl -s localhost:8000/api/health/live            # 进程活着吗
curl -s localhost:8000/api/health/ready | head -c 400   # 依赖（数据库/配置加密）就绪吗
tail -n 200 logs/backend.log      # 本地开发日志
docker compose logs --tail=200 backend            # 容器日志
```

| 症状 | 优先检查 |
| :--- | :--- |
| 页面打不开 / 502 | 后端进程、`/api/health/ready`、Nginx 反代配置 |
| 页面能开但没有数据 | 数据源链路（[第四节](#四行情与数据)）、后端日志里的 `provider call failed` |
| AI 功能报错 | LLM 配置（[第五节](#五llm-与-ai-能力)）、`llm_*` 配置项 |
| 分析任务不动 | 工作流队列与租约（[第六节](#六工作流与任务队列)） |
| 收不到推送 | 通道配置与防抖（[第七节](#七推送通知)） |

> [!TIP]
> 需要看完整路由与参数时，本地启动加 `APP_EXPOSE_DOCS=1`（如 `APP_EXPOSE_DOCS=1 make backend-dev`），
> 然后访问 `http://127.0.0.1:8000/docs`。生产环境默认关闭该文档端点。

## 二、启动与部署

### 容器起不来 / 一直是 unhealthy

1. `docker compose ps` 看是哪个容器退出；`docker compose logs backend` 看首个异常栈。
2. 常见原因：`.env` 未生成 `CONFIG_ENCRYPTION_KEY`（启动时校验失败）、
   `data/` 或 `logs/` 未创建、端口被占用（`DOCKER_FRONTEND_PORT` 冲突）。
3. 就绪检查用的是 `/api/health/ready`：数据库不可写或配置加密密钥缺失时会返回未就绪，
   此时健康检查会一直失败，而不是"进程挂了"。

### 挂载目录权限错误（Permission denied）

容器以 UID/GID `1000:1000` 运行：

```bash
sudo chown -R 1000:1000 data logs
```

### 端口冲突

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN     # 后端
lsof -nP -iTCP:5173 -sTCP:LISTEN     # 前端 dev
```

前端对外端口用 `.env` 的 `DOCKER_FRONTEND_PORT` 调整；本地开发用 `BACKEND_PORT` / `FRONTEND_PORT`。

### 首次管理员密码丢了

密码只在**首次启动**时打印到后端日志。之后可以无损重置（不影响业务数据）：

```bash
make backend-reset-admin ADMIN=admin PASS='新密码'          # 本地
docker compose exec backend python scripts/reset_admin_password.py admin --password '新密码'   # 容器
```

重置会同时解除禁用、标记已激活，并让该账号在其它设备上的旧登录凭据失效。

## 三、登录与账号

| 现象 | 说明与处置 |
| :--- | :--- |
| 登录后强制跳转改密页 | 账号 `must_change_password=true`，改密后恢复；重置密码脚本会清掉该标记 |
| 注册提示需要邀请码 | 普通用户必须用邀请码：管理员在「系统设置 → 邀请码管理」生成 |
| 401 / 会话频繁失效 | Cookie 失效或系统时间偏差过大；核对容器时区（默认 `TZ=Asia/Shanghai`） |
| 想清空本地所有账号 | `make backend-reset-accounts`（会重建账号体系数据，谨慎使用） |

## 四、行情与数据

### 页面数据为空或大面积缺失

```bash
grep -E "provider call failed|exhausted retries|circuit|熔断|限流" logs/backend.log | tail -30
```

处置顺序：

1. **确认是上游还是本机**：`curl -sI https://push2.eastmoney.com` 之类的手工探测；
   若整机出网受限，配置 `.env` 的 `OUTBOUND_PROXY_TYPE` / `OUTBOUND_PROXY_URL`
   （只作用于声明了 `ProxyScope` 的接口，未声明的保持直连）。
2. **等冷却**：上游按 IP 限流时会出现 `200 + 空体`，网关按 `transient` 处理并计数，
   达到 `PROVIDER_FAILURE_THRESHOLD`（默认 3）后熔断 `PROVIDER_CIRCUIT_OPEN_SECONDS`（默认 30 秒）。
   冷却结束后半开探测会自动恢复，无需重启。
3. **换源验证**：同一份数据通常有多源降级（见 [数据源与降级机制](data-sources.md)），
   若某一家长期失败而其余正常，可在设置页调整或等待上游修复。

### 日线归档没有当天数据

- 归档是两阶段：**16:20 首次预归档**、**17:00 最终复核**（`provisional` → `confirmed`）。
  未到时间点不会有 `confirmed` 数据，依赖"当日已确认收盘价"的功能会留空而不是拿旧价冒充。
- 管理员可在「系统配置 → 行情归档」查看状态并手动刷新/重试；回填任务支持断点续跑与
  "跳过已有数据/覆盖已有数据"两种模式。
- 复权因子异常：`cd backend && uv run python -m app.scripts.reconcile_adjustment_factors`
  巡检并修复；该脚本只读扫描 + 按需重算。

### 行业库 / 概念数据为空

```bash
make backend-db-init        # 建表 + 空行业库自动播种
make backend-seeds-drift    # 对比运行库与种子快照（只读）
make backend-export-seeds   # 用运行库反导出种子（确认后再提交）
```

行业映射由后台任务周期性刷新（新浪申万映射 → 行业库），留意日志
`申万行业数据库周期更新完成`。概念标签可在「基础数据管理」页同步。

### 数据库被锁 / 写入很慢

- 系统使用 SQLite WAL 模式 + 读写分离，正常情况下并发阻塞应很少。
  日志出现 `database is locked` 时先看是否有容器重复启动抢同一份 `data/`。
- 磁盘占满会导致 WAL 无法 checkpoint：`df -h`、清理 `data/db/backups/` 旧备份。

## 五、LLM 与 AI 能力

| 报错/现象 | 原因 | 处置 |
| :--- | :--- | :--- |
| `缺少 API Key，请在设置页填写个人 API Key，或由管理员配置全局 Key` | 当前用户与全局都没有可用 Key | 个人设置页填 Key，或让管理员配置全局 `LLM_API_KEY` |
| `Base URL 被出网策略拒绝：目标 x.x.x.x 属于内网地址` | 默认禁止 LLM 指向 RFC1918/ULA | 本机 Ollama 用 `127.0.0.1` 无需设置；同机 docker 服务名或内网网关需要 `LLM_ALLOW_PRIVATE_ENDPOINTS=true` |
| `Base URL 被出网策略拒绝：目标 ... 属于元数据/链路本地网段` | 指向云元数据或链路本地地址 | 这是安全拦截且不可关闭，请改回正常网关地址 |
| 401 / 403 | Key 无效或无该模型权限 | 检查 Key 与 `LLM_MODEL` 是否匹配 provider |
| 429 / 余额不足 | 上游限流或额度耗尽 | 换 Key/降频；单用户触发频率受 `USER_LLM_RATE_LIMIT_REQUESTS`（默认 20/60 秒）限制 |
| 请求超时 | 首字慢或生成过长 | 调大 `LLM_TIMEOUT_SECONDS`、`LLM_GENERATION_TIMEOUT_SECONDS`，或调小输出预算 |
| 模型不支持工具调用 | 少数聚合网关拒绝 `tools` 参数 | 系统会自动降级为纯文本工具协议并记录该路由，30 分钟内不再尝试原生工具；无需手工干预 |
| 思考模型报 `temperature` 不支持 | 如 DeepSeek v4+ 系列 | 系统按模型世代自动关闭 temperature 并回放 `reasoning_content`，无需手工配置 |
| 网关私有开关不生效 | 需要透传厂商字段 | 用 `LLM_EXTRA_BODY`（JSON）或设置页「高级」里的额外字段，受治理字段会被拒绝 |

> [!NOTE]
> `deepseek-v4` 及之后的世代、`deepseek-reasoner`/`deepseek-flash` 都会被识别为思考模型；
> `*-chat` / `*-instruct` 保持普通行为。若新世代默认不再是思考模型，把对应标记加入
> `backend/app/infrastructure/llm/capabilities.py` 的排除集合即可。

### 排查顺序建议

1. 设置页确认 provider / base_url / model / key 四要素；
2. 看后端日志里 `llm` 相关的 401/429 与降级提示；
3. 用设置页的「获取模型列表」（`POST /api/settings/llm/models`）验证地址与 Key 是否可达。

## 六、工作流与任务队列

- 查询进行中任务：`GET /api/workflows/active`；单个任务详情 `GET /api/workflows/{job_id}`。
- 取消任务：`DELETE /api/workflows/{job_id}`。取消在数秒内生效（心跳续租周期 ≤5 秒），
  不必重启服务。
- 提示 `任务队列已满，请等待已有任务完成`：单个用户同时运行的任务数有上限，
  等已有任务结束或先取消。
- 服务多副本时任务由主节点 worker 执行（基于租约），若任务长期 `running` 且无进展，
  检查日志中的 `Workflow Job` 与租约相关记录，确认 worker 存活、`data/` 未被多个实例共享。

## 七、推送通知

| 现象 | 排查 |
| :--- | :--- |
| 完全收不到 | 日志 `未检测到有效配置的推送通道` → 「系统配置 → 推送」里通道未启用或缺 Webhook；用 `POST /api/push/test-webhook` 发测试消息 |
| 只收到一半 | 3 分钟内同类事件会**防抖**跳过（`触发通知防抖机制，跳过重复投递`），属预期行为 |
| 飞书报签名/权限错误 | 检查 `FEISHU_APP_ID/SECRET`、机器人是否在群内、云文档目录 Token 是否有权限 |
| 钉钉报 sign 不匹配 | 加签密钥与机器人一致；确认容器时间正确（加签依赖时间戳） |
| 想看投递历史 | `GET /api/push/history`（前端设置页可查看并可清空） |
| 手动触发一次 | 管理员页面的「立即推送」或在设置页发测试消息，避免等定时任务 |

## 八、前端

| 现象 | 处置 |
| :--- | :--- |
| 白屏 / 页面很旧 | 强制刷新；容器部署确认 Nginx 已换新产物（`make docker-build`） |
| 长任务进度丢失 | 进度已由全局工作流运行时接管，切页面会重连 SSE；若仍丢失，看浏览器控制台是否有连接失败 |
| SSE 反复重连 | 单次请求最多重连 4 次后报中断。SSE 响应带 `X-Accel-Buffering: no`，自建反代需保留该头并保证读超时大于心跳间隔（默认 15 秒心跳，仓库内 Nginx 配的是 `proxy_read_timeout 300s`） |
| 构建内存不足 | 提高 Node 内存：`NODE_OPTIONS=--max-old-space-size=4096 npm run build` |

## 九、备份与恢复

- 备份位置：`data/db/backups/<db>-<UTC时间戳>.sqlite3.gz` + `.sha256` 校验文件；
  默认保留 2 份（`DATABASE_BACKUP_RETENTION_COUNT` 可调，设置页保存后下一轮生效）。
- 恢复必须先停服，再执行（详见 [README「备份与离线恢复」](../README.md#备份与离线恢复)）：

```bash
docker compose down
docker compose run --rm --no-deps backend \
  python -m app.scripts.restore_database_backup market /app/data/db/backups/market-YYYY....sqlite3.gz \
  --confirm-backend-stopped
docker compose up -d
```

- 校验失败（`quick_check` 不通过）时不要覆盖现有库，先保留现场再排查磁盘/内存问题。

## 十、收集诊断信息

报问题时建议附上：

```bash
cd backend && uv run python scripts/verify_application_runtime.py   # 运行时自检
curl -s -H "Authorization: Bearer <token>" localhost:8000/api/health/metrics | head -c 2000
curl -s localhost:8000/api/system/version
```

以及 `logs/backend.log` 中出错时间点前后 200 行（注意先脱敏 API Key、Cookie 与账号信息）。

## 十一、相关文档

- [数据源与降级机制](data-sources.md)
- [配置系统开发指南](configuration.md)
- [本地开发指南](development.md)
- [自动推送与通知配置](push-notifications.md)
