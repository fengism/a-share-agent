from app.agentic.skills.contracts import Skill

SKILLS = (
    Skill(
        name="url_content",
        description="网页阅读与对比",
        triggers=("消息包含 HTTP(S) 链接", "阅读、总结或对比网页内容"),
        activation_keywords=("阅读", "总结", "网页内容", "对比网页"),
        tool_names=("fetch_url", "fetch_urls"),
        rules=(
            "单个链接用 fetch_url；多个链接一次性用 fetch_urls。",
            "默认使用 mode=auto；明确需要 JS 渲染时用 dynamic，普通 HTTP 被反爬拦截时用 stealth。",
            "仅依据抓取正文作答；抓取失败时说明原因，不补写原文没有的信息。",
        ),
        exclusions=("不要自动联动股票工具，除非用户明确要求结合行情分析",),
        priority=10,
    ),
    Skill(
        name="twitter_account",
        description="Twitter/X 账号观点分析",
        triggers=("明确要求分析某个 Twitter/X 用户或财经账号",),
        activation_keywords=("twitter 账号", "twitter账号", "x 账号", "x账号", "推特账号"),
        tool_names=("analyze_twitter_user",),
        rules=("调用 analyze_twitter_user，仅传用户名且不含 @；基于工具结果作答。",),
        exclusions=("普通推文链接使用 fetch_url，不要启动账号级分析",),
        priority=20,
    ),
    Skill(
        name="information_query",
        description="公开网页、资讯检索与自然语言结构化查询",
        triggers=("搜索互联网或查找公开网页", "查找研报、公告或新闻", "无法映射为固定工具参数的数据查询"),
        activation_keywords=("搜索", "查找", "检索", "网页", "白皮书", "公开来源", "资料来源"),
        tool_names=("web_search", "fetch_url", "fetch_urls", "iwencai_search", "iwencai_query"),
        rules=(
            "公开互联网网页和通用资料先用 web_search；搜索结果只用于发现候选页面，不视为完整正文。",
            "今日或最新资讯将 time_range 设为 day，近期动态设为 week，普通检索默认 half_year；仅历史或静态资料使用 any。",
            "默认使用中文关键词并设置 language=zh；仅在中文资料不足时补充英文权威来源。",
            "用户需要详细内容时，必须对 web_search 返回的 URL 调用 fetch_url；需要阅读多个结果时调用 fetch_urls。",
            "研报、公告或财经新闻优先用 iwencai_search；非选股的结构化数据问题用 iwencai_query。",
        ),
        exclusions=("选股问题使用 iwencai_select_stock 或 screen_stocks",),
        priority=70,
    ),
)
