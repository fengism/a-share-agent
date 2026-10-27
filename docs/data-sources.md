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
- **可选项**：`eastmoney`（东方财富）、`ths`（同花顺）、`cls`（财联社）、`sina`（新浪财经）、`akshare`（AkShare）；
- **生效规则**：底层网络层（`client.py` / `ThsTransport` / `SinaDataProvider`）根据用户勾选的 `outbound_proxy_scopes` 动态决定是否走代理；未勾选的源保持海外直连（如新浪行情直连延迟更低更稳）。

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
