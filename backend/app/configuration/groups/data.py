"""数据源凭证/限流与网络出站配置分组。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.configuration.groups.base import ConfigGroup


class DataSourceGroup(ConfigGroup):
    """行情/宏观/搜索数据源的凭证与东财 IP 级限流参数。"""

    PREFIX = ""

    eastmoney_cookie: str = ""
    fred_api_key: str = ""
    # fuyao（同花顺金融数据 API）兜底数据源密钥，供涨跌停/炸板/估值接口使用。
    fuyao_api_key: str = Field(default="", repr=False)
    baidu_cookie: str = ""
    baidu_acs_token: str = ""
    ths_cookie: str = ""
    legulegu_token: str = ""
    anysearch_api_key: str = Field(default="", repr=False)
    twitter_feeds: list[str] = Field(default_factory=lambda: ["qinbafrank"])
    twitter_post_retention_days: int = 90

    eastmoney_min_interval_seconds: float = 1.0
    eastmoney_datacenter_min_interval_seconds: float = 1.0
    eastmoney_datacenter_cooldown_seconds: float = 10.0
    eastmoney_jitter_min_seconds: float = 0.1
    eastmoney_jitter_max_seconds: float = 0.5
    eastmoney_cooldown_seconds: float = 120.0
    eastmoney_transient_failure_threshold: int = 3


class NetworkGroup(ConfigGroup):
    """出站代理、Web 抓取、行情 SDK 与 CORS 等网络参数。"""

    PREFIX = ""

    http_trust_env: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    web_fetch_max_response_bytes: int = Field(default=20 * 1024 * 1024, ge=64 * 1024, le=100 * 1024 * 1024)
    web_fetch_browser_enabled: bool = True
    web_fetch_browser_timeout_seconds: float = Field(default=20.0, ge=5.0, le=120.0)
    web_fetch_browser_settle_seconds: float = Field(default=10.0, ge=0.0, le=15.0)
    web_fetch_browser_max_concurrency: int = Field(default=2, ge=1, le=8)
    # 公共出站代理：供按出口 IP 风控的上游接口统一使用（当前为东财 K 线与资金流）。
    # 各 provider 在代码里声明自己的 ProxyScope，未声明的接口一律保持直连。
    outbound_proxy_type: Literal["none", "http", "socks5"] = "none"
    outbound_proxy_url: str = ""
    outbound_proxy_timeout_seconds: float = Field(default=20.0, ge=5, le=120)
    outbound_proxy_retries: int = Field(default=2, ge=0, le=6)
    # 允许走代理的数据源接口作用域列表（如 eastmoney、ths、cls、sina、akshare）
    outbound_proxy_scopes: list[str] = Field(default_factory=lambda: ["eastmoney"])
    tdxhub_timeout_seconds: float = Field(default=5.0, gt=0)
    # 客户端重建失败的冷却窗口。SDK 每次重建都会全量探测候选行情服务器，
    # 冷却期内快速失败可避免故障期间反复付出探测代价；到期后自动重新探测，
    # 恢复的服务器会自然重新参与，因此该值只影响恢复延迟、不影响可用性。
    tdxhub_rebuild_cooldown_seconds: float = Field(default=30.0, ge=0, le=600)
    # 后台 TDX 行情服务器测速任务的执行周期。
    tdxhub_bestip_refresh_seconds: float = Field(default=1800.0, gt=0, le=86400)
    # 单次历史资金流备选查询的总 I/O 预算（包含连接、分页和逐日聚合）。
    tdxhub_fund_flow_timeout_seconds: float = Field(default=60.0, gt=0, le=90)
    sina_hq_page_workers: int = Field(default=4, ge=1, le=8)
