# 数据源与降级机制

说明数据从哪来、失败时怎么退、如何判断数据是否可信，以及新增一个数据源要改哪里。

## 一、Provider 清单

Provider 由 `backend/app/infrastructure/providers/registry.py` 的 `_PROVIDER_EXPORTS` 注册，
按稳定短名懒加载单例。`get_provider("eastmoney")` 即可拿到实例。

### 行情与日线

| Provider | 用途 |
| :--- | :--- |
| `tdxhub` | 通达信 SDK 进程内直连：实时行情、个股/指数 K 线、名称、F10 与财务基础信息 |
| `sina` | 新浪财经：全市场快照、行业映射、K 线、分时、财务（主力备用源） |
| `tencent` | 腾讯财经：实时行情、指数分时与 K 线、概念板块、板块涨跌排行 |
| `akshare` | AkShare 封装：备用行情与财务数据 |
| `sina_hk` | 新浪港股行情 |
| `cls` | 财联社不复权行情、快讯、市场情绪 |

### 指数、板块与资金

| Provider | 用途 |
| :--- | :--- |
| `eastmoney` | 东方财富：行情、资金流、板块、龙虎榜（有 IP 级限流） |
| `kaipanhong` | 开盘红：涨停梯队、板块资金 |
| `ths` | 同花顺：热股/概念热榜、资金数据 |
| `baidu` | 百度股市通：涨跌停与部分行情接口 |
| `fuyao` | 同花顺金融数据 API：涨跌停/炸板/估值的付费兜底源 |

### 名录、基本面与估值

| Provider | 用途 |
| :--- | :--- |
| `exchange` | 上交所/深交所/北交所官方名录：上市股票清单与板块归属 |
| `cninfo` | 巨潮资讯：全市场代码与名称索引、公告 |
| `legulegu` | 乐咕乐股：公开市场估值数据 |
| `iwencai` | 问财：自然语言选股（需 API Key） |

### 宏观

| Provider | 用途 |
| :--- | :--- |
| `nbs` | 国家统计局：物价、景气等国内宏观指标 |
| `fred` | 美联储 FRED：美国宏观指标（需 API Key） |
| `sge` | 上海黄金交易所：黄金现货历史行情 |

### 资讯与检索

| Provider | 用途 |
| :--- | :--- |
| `rss` | RSS/Atom 财经媒体新闻 |
| `twitter` | 通过 fxtwitter 拉取 X/Twitter 财经账号内容 |
| `anysearch` | AnySearch 聚合检索（支持多 Key 轮询与配额冷却） |
| `baidu_search` / `bing_cn_search` / `so360_search` / `google_search` | 无 Key 公共搜索引擎抓取，作为检索兜底 |

### tdxhub 直连说明

- 依赖固定为 `tdxhub-sdk==0.5.1`（该版本把个股实时快照与指数 K 线全面切到 round2，
  并给 `bars()` 加了显式指数开关），
  由 `backend/app/infrastructure/providers/tdxhub.py` 进程内调用，共享单例 `SharedTdxhubQuotes`
  （`Quotes.factory(market="std")`）。
- 共享实例有两个：普通行情用 `shared_tdxhub_quotes`，历史资金流用 `shared_tdxhub_raise_quotes`
  （`raise_exception=True`，否则资金流失败会返回 `None` 而被误判成「当日缺少分笔资金」）。
  两者各自单飞重建、各自冷却，但都只做**一次**全量服务器探测；资金流不再每次查询新建客户端。
- 重建失败按连续失败次数**指数退避**进入冷却：从 `TDXHUB_REBUILD_BACKOFF_BASE_SECONDS`（默认 2s）
  起翻倍，封顶 `TDXHUB_REBUILD_COOLDOWN_SECONDS`（默认 30s），并带向下抖动。瞬时抖动只需停几秒，
  持续故障才拉长到上限；重建成功后计数归零。
- 客户端重建优先用后台测速写回的 `BESTIP.HQ`（内存）做单节点建连（~2-3s）；该节点不可用时
  立即回退对 `SERVER.HQ` 的全量并发探测（~6-7s），因此不牺牲可用性。重建成功后会把实际连上的
  节点写回 `BESTIP.HQ`，让下一次重建继续走快路径。
- K 线默认走 round2 新协议（旧 `0x052d` 命令已被部分服务器停用）；
  设置 `TDXHUB_KLINE_PROTOCOL=legacy` 可强制先走经典命令，失败再降级 round2。
- 个股 K 线与个股行情走 `bars` / `quotes()`：0.5.0 的 `quotes()` 已把快照切到 round2
  （`0x054c`），经典 `get_security_quotes` 返回空时自动降级，因此本层不再自建 round2 连接。
- 指数 K 线：`bars(index=True)`（0.5.1 新增的显式指数开关，按指数记录结构解析、含涨跌家数），
  个股 K 线仍走不带该开关的 `bars`。指数必须带市场前缀（裸 `000001` 会被当成平安银行），
  返回的 vol 为「手」，统一 ×100 得到股。
- 实时快照的“缺失代码”容错：服务端只返回有效代码的记录并严格比对条数，一只退市/改代码的
  股票就会让整批报 `ProtocolError`。因此按 80 只分块请求，失败批次用二分剔除定位并记入
  1 小时负缓存（下次直接跳过）；只有本批已成功过才把单码失败记为“无快照”，避免链路异常
  把整批有效代码误标。多块共享一份二分预算（单批 6s / 总量 10s），耗尽时返回已拿到的部分
  结果，其余代码交给 `tencent` / `sina` / `fuyao` 兜底。
- 支持出网代理：在设置页「出站代理 → 走代理的接口与数据源」勾选 **通达信（TDX）**，
  即由 `outbound_proxy_scopes` 中的 `tdxhub` 控制（见“四、限流与出站代理”）；未勾选则直连。

## 二、多源降级链

业务层用 `BaseProviderChain(attempts, operation=...)` 声明"按顺序尝试的多源候选"，
核心实现见 `backend/app/infrastructure/providers/provider_chain.py`：

```python
source, items = await BaseProviderChain(
    [ProviderAttempt("tdxhub", ...), ProviderAttempt("tencent", ...)],
    operation="stock_kline",
).run()
```

- `run()` 返回第一个成功结果；`run_with_report()` 额外返回每次尝试的错误，便于日志与诊断。
- 典型链路构造位置：实时行情 `financial_data/stock/quotes/realtime.py`、
  历史 K 线 `financial_data/stock/quotes/historical.py`、指数 `financial_data/market/quotes/indices.py`。
- 全市场历史日线回填使用固定优先级并及时校验：
  `TDX → 腾讯 → AkShare(新浪) → 东方财富直连 → 新浪直连 → 财联社`，
  每条 **至少两个独立来源** 在日期、OHLC、成交量与成交额上一致才入库。

## 三、失败分类、重试与熔断

错误先被 `provider_policy.classify_provider_error()` 归类，再决定"重试 / 熔断 / 直接放弃"：

| 分类 | 触发条件 | 处理 |
| :--- | :--- | :--- |
| `timeout` | 请求超时 | 重试（受重试预算约束） |
| `rate_limit` | HTTP 429 或上游限流异常 | 退避后重试 |
| `transient` | 5xx、连接错误、**200 但空体**（常见于 IP 级限流） | 重试并计入熔断 |
| `permanent` | 4xx（除 429）、协议/证书错误 | 不重试，直接切换下一个源 |
| `circuit_open` | 熔断器处于打开状态 | 立即跳过该 provider.operation |

熔断按 `(provider, operation)` 维度计数，命中阈值后直接快速失败，避免每次请求都把整条链跑一遍
（`provider_circuit.py`，半开状态只放行一个探针请求）。

相关配置（`backend/app/configuration/groups/research.py`，均可在 `.env` 覆盖）：

| 配置项 | 默认 | 含义 |
| :--- | :--- | :--- |
| `provider_gateway_max_attempts` | 2 | 单次调用最多尝试次数 |
| `provider_failure_threshold` | 3 | 连续失败多少次打开熔断 |
| `provider_circuit_open_seconds` | 30 | 熔断打开时长 |
| `provider_retry_base_seconds` | 0.2 | 指数退避基数 |
| `provider_retry_budget_seconds` | 5 | 单次调用重试总预算 |
| `provider_retry_jitter_seconds` | 0.1 | 退避抖动，避免同刻打满上游 |

## 四、限流与出站代理

### 出站代理路由
针对海外云厂商 IP 被部分国内数据源屏蔽（如东方财富历史 K 线连接重置、财联社主线频控），系统支持配置统一出站代理，并按接口作用域细粒度控制生效：
- **可选项**：`eastmoney`（东方财富）、`ths`（同花顺）、`cls`（财联社）、`sina`（新浪财经）、`akshare`（AkShare）、`tdxhub`（通达信直连）；
- **生效规则**：底层网络层（`client.py` / `ThsTransport` / `SinaDataProvider`）根据用户勾选的 `outbound_proxy_scopes` 动态决定是否走代理；未勾选的源保持海外直连（如新浪行情直连延迟更低更稳）。
- **通达信直连（`tdxhub`）例外**：行情客户端直连行情服务器 IP:端口，不经过 HTTP，无法按主机名筛选，因此选中 `tdxhub` 后整条 TDX 链路走代理；
  该链路自带 SOCKS5/HTTP CONNECT 握手实现，无需安装 PySocks，代理配置变更后共享客户端会自动重建。
- **TDX 连通性测试**：勾选 `tdxhub` 且代理开启后，设置页会多出「测试 TDX 连通性」按钮
  （`POST /api/config/proxy/test-tdx`）。它先建代理隧道、再向行情节点发一次 round2 协议请求，
  因此能区分「代理隧道不可用」与「代理正常但目标节点行情接口异常」——普通 `HTTP` 探测对原始 TCP 无效。
  探测成功会顺便提前解除两个共享客户端的重建冷却，让下一次业务请求立即重试（失败不动冷却，避免探测风暴）。

### 请求限流防线
两条独立防线，避免把上游打到反爬或 IP 封禁：

1. **并发信号量**（`app/core/concurrency/rate_limiter.py`）：按数据源拆分，
   如 `eastmoney_semaphore`(1)、`akshare_semaphore`(2)、`sina_semaphore`(2)、
   `search_semaphore`(2)、`iwencai_semaphore`(1) 等。搜索引擎单独限流，因为百度按
   IP + 指纹判定，并发过高会直接返回安全验证空壳页。
2. **IP 级节流**（`eastmoney_*` 配置）：最小请求间隔、随机抖动、冷却时间与瞬时失败阈值。
   AnySearch 另有按 Key 的配额冷却：429/402 触发冷却，401/403 永久禁用该 Key。

## 五、数据质量校验

失败可以重试，**错误的数据比缺失的数据更危险**，因此关键链路带质量门：

- **全市场快照**：校验行数是否等于预期股票数、代码去重、价格/成交量正值比例、
  `成交额 ÷ (成交量 × 价格)` 中位数是否接近 1。不达标按失败处理并沿用上一份快照。
- **历史日线**：多源交叉校验（≥2 源一致），并按质量评分记录到回填任务明细。
- **复权因子**：本地仿射因子优先；因子覆盖的交易日期与本地日线不一致、算法版本过旧或结果过期时，
  自动重新推导，可用 `python -m app.scripts.reconcile_adjustment_factors` 巡检修复。
- **交易日历**：交易所日历缺失年份时降级为工作日判断，并由采集器的行情日期二次兜底。

## 六、缓存

`app/core/cache.py` 的 `market_cache` 统一管理 TTL，各业务域的策略常量集中在
`app/core/cache_policies.py`（分钟行情、板块资金、概念联动等各不相同）。可调项举例：

| 配置项 | 默认 | 含义 |
| :--- | :--- | :--- |
| `CACHE_TTL_ANALYSIS` | 14400 | 分析结果缓存有效期（秒） |
| `PORTFOLIO_QUOTE_CACHE_TTL_SECONDS` | 10 | 持仓/自选行情缓存 |
| `PORTFOLIO_QUOTE_STALE_TTL_SECONDS` | 300 | 行情过期后仍可用的兜底时长 |

缓存只用于降低上游压力，不替代质量校验：命中缓存的数据同样来自此前通过校验的那一份。

## 七、新增一个 Provider

1. 在 `app/infrastructure/providers/<name>.py` 实现类，设置 `name = "<name>"`，方法签名与既有
   provider 保持一致（返回统一领域模型，如 `KlineItem`、`QuoteSet`）。
2. 在 `registry.py` 的 `_PROVIDER_EXPORTS` 注册短名 → (模块, 单例属性)，保持懒加载。
3. 在业务模块的链路里加入 `ProviderAttempt("<name>", ...)` 的合适顺序（按可靠性/成本/延迟排序）。
4. 为该 provider 的**解析函数**补离线 fixture 测试（把一次真实响应存成 JSON 后断言解析结果）。
   这类模块最容易因上游改字段而静默失效，当前 `anysearch` 已提供可复制的写法
   （`backend/tests/test_provider_anysearch_and_news.py`）。
5. 若需要凭据，加到 `backend/app/configuration/groups/data.py` 并在 `.env.example` 记录，
   同步跑 `make check`（配置一致性测试会校验默认值与文档）。

## 八、相关文档

- [故障排查手册](troubleshooting.md) — 数据源失败时的定位步骤
- [架构与边界](architecture.md) — Provider 层在分层中的位置
- [配置系统开发指南](configuration.md) — 新增配置项的完整流程
