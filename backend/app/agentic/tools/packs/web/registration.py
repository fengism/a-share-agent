"""Web Tool Schema 与执行策略注册。"""

from collections.abc import Callable
from typing import Any

from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.agentic.tools.packs.web.search import DEFAULT_SEARCH_ENGINE

WEB_FETCH_POLICY = ToolPolicy(
    cost="high", cache_ttl_seconds=300, timeout_seconds=90, max_parallel_calls=2
)
WEB_BATCH_POLICY = ToolPolicy(
    cost="high", cache_ttl_seconds=300, timeout_seconds=120, max_parallel_calls=1
)
WEB_SEARCH_POLICY = ToolPolicy(cost="medium", cache_ttl_seconds=300)
TWITTER_ANALYSIS_POLICY = ToolPolicy(
    cost="high",
    cache_ttl_seconds=900,
    timeout_seconds=120,
    max_parallel_calls=2,
)


def register_web_tools(
    fetch_url_executor: Callable[..., Any],
    fetch_urls_executor: Callable[..., Any],
    search_executor: Callable[..., Any],
    read_pdf_executor: Callable[..., Any] | None = None,
    *,
    target_registry: CapabilityCatalog = registry,
    fetch_policy: ToolPolicy = WEB_FETCH_POLICY,
    batch_policy: ToolPolicy = WEB_BATCH_POLICY,
    search_policy: ToolPolicy = WEB_SEARCH_POLICY,
) -> None:
    """Register web search and URL fetching tools."""
    target_registry.register_tool(
        Tool(
            name="web_search",
            description=(
                "搜索公开互联网网页，返回标题、URL 和摘要。"
                "当用户要求搜索网页、查找公开资料，或尚未提供具体 URL 时调用。"
                "默认使用 Bing 中国、优先中文结果并限定最近半年，可选百度或 Google。"
                "搜索结果不是网页全文；用户需要详细内容时，必须使用返回的 URL 继续调用 fetch_url，"
                "需要阅读多个结果时调用 fetch_urls。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 200,
                        "pattern": r"\S",
                        "description": (
                            "简洁搜索关键词组合，包含核心实体和单一研究维度；"
                            "时效性检索应结合运行时当前年份或‘最新’，不要复制完整问题或混合多个维度。"
                        ),
                    },
                    "engine": {
                        "type": "string",
                        "enum": ["baidu", "bing_cn", "google"],
                        "default": DEFAULT_SEARCH_ENGINE,
                        "description": "搜索引擎；Google 通常需要配置代理。",
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                        "description": "最多返回的搜索结果数量。",
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["day", "week", "month", "half_year", "any"],
                        "default": "half_year",
                        "description": (
                            "搜索结果时间范围：day 最近一天、week 最近一周、"
                            "month 最近一月、half_year 最近半年、any 不限时间。"
                            "实时资讯优先使用 day 或 week。"
                        ),
                    },
                    "language": {
                        "type": "string",
                        "enum": ["zh", "any"],
                        "default": "zh",
                        "description": "结果语言偏好：zh 优先中文结果，any 不限制语言。",
                    },
                },
                "required": ["query"],
            },
            policy=search_policy,
            executor=search_executor,
        )
    )
    target_registry.register_tool(
        Tool(
            name="fetch_url",
            description=(
                "抓取指定 URL 的网页内容并提取正文文本（Markdown 格式）。"
                "当用户发送链接/URL、要求阅读网页、总结文章内容时调用。"
                "支持新闻、博客、研报（PDF）、X/Twitter 推文等公开网页。"
                "返回内容包含 meta 信息（标题、描述、发布时间）和结构化正文。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "format": "uri",
                        "maxLength": 2048,
                        "description": "要抓取的网页 URL 地址，如 https://finance.sina.com.cn/...",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "http", "stealth", "dynamic"],
                        "default": "auto",
                        "description": "抓取模式：auto 自动降级，http 仅安全 HTTP，stealth 反爬浏览器，dynamic JS 渲染浏览器。",
                    },
                },
                "required": ["url"],
            },
            policy=fetch_policy,
            executor=fetch_url_executor,
        )
    )
    target_registry.register_tool(
        Tool(
            name="fetch_urls",
            description=(
                "批量并发抓取多个 URL 的网页内容并提取正文文本。"
                "当用户要求同时查看多篇文章、对比多个网页内容时调用。"
                "最多支持 10 个 URL。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string", "format": "uri", "maxLength": 2048},
                        "minItems": 1,
                        "maxItems": 10,
                        "uniqueItems": True,
                        "description": "要抓取的 URL 列表，如 [\"https://...\", \"https://...\"]",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "http", "stealth", "dynamic"],
                        "default": "auto",
                        "description": "抓取模式：auto 自动降级，http 仅安全 HTTP，stealth 反爬浏览器，dynamic JS 渲染浏览器。",
                    },
                },
                "required": ["urls"],
            },
            policy=batch_policy,
            executor=fetch_urls_executor,
        )
    )
    if read_pdf_executor is not None:
        target_registry.register_tool(
            Tool(
                name="read_pdf",
                description=(
                    "下载并深度阅读 PDF 格式的券商研报、上市公司定期财报（年报/半年报）或官方公告。"
                    "支持提取指定页码范围的正文段落及结构化 Markdown 表格。"
                    "当搜索或网页链接指向 .pdf 文件，或者需要研读完整报告原文时调用。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "PDF 文档的在线 URL 地址（http/https 均可，如 https://.../report.pdf），或应用数据目录内的本地 .pdf 路径",
                        },
                        "start_page": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 1,
                            "description": "起始阅读页码（从 1 开始计数，默认第 1 页）",
                        },
                        "max_pages": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 20,
                            "description": "本次提取的最大页数（默认 20 页）",
                        },
                        "extract_tables": {
                            "type": "boolean",
                            "default": True,
                            "description": "是否解析并提取 PDF 中的结构化数据表格为 Markdown 表格",
                        },
                    },
                    "required": ["url"],
                },
                policy=fetch_policy,
                executor=read_pdf_executor,
            )
        )


def register_twitter_tools(
    analyze_executor: Callable[..., Any],
    *,
    target_registry: CapabilityCatalog = registry,
    policy: ToolPolicy = TWITTER_ANALYSIS_POLICY,
) -> None:
    """Register the Twitter account analysis tool."""
    target_registry.register_tool(
        Tool(
            name="analyze_twitter_user",
            description="分析指定 Twitter/X 用户的最新推文与长文并生成中文报告。该工具成本较高，仅在用户明确要求分析某个账号时调用。",
            parameters={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "pattern": r"^[A-Za-z0-9_]{1,15}$",
                        "description": "Twitter 用户名，不含 @ 符号，例如 qinbafrank",
                    },
                },
                "required": ["username"],
            },
            policy=policy,
            executor=analyze_executor,
        )
    )
