"""每日复盘新闻与政策事件筛选、归类和确定性影响提示。"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Iterable, cast
from urllib.parse import urlsplit

from app.core.news import parse_news_datetime
from app.core.timezones import SHANGHAI_TIMEZONE
from app.domain.news import NewsSearchItem
from app.modules.daily_review.models import PolicyNewsSnapshotItem

_POLICY_KEYWORDS = (
    "国务院", "中央", "政治局", "发改委", "央行", "证监会", "财政部", "商务部", "工信部",
    "住建部", "国资委", "政策", "通知", "意见", "规划", "指导", "监管", "改革", "试点",
    "降准", "降息", "LPR", "再贷款", "增发国债", "专项债", "减税", "补贴", "贴息", "购房补贴",
    "购房", "买房", "首套房", "住房贷款", "按揭补贴", "房贷补贴", "以旧换新",
)
_MACRO_KEYWORDS = (
    "GDP", "CPI", "PPI", "PMI", "社融", "M2", "新增贷款", "就业", "出口", "进口",
    "汇率", "人民币", "国债收益率", "流动性", "通胀", "经济数据",
)
_GLOBAL_KEYWORDS = (
    "美联储", "FOMC", "美元", "美债", "关税", "制裁", "地缘", "冲突", "OPEC", "原油",
    "欧洲央行", "日本央行", "海外市场", "中美", "贸易摩擦",
)
_INDUSTRY_KEYWORDS = (
    "行业", "产业", "产能", "价格", "涨价", "降价", "订单", "招标", "集采", "出口管制",
    "技术突破", "商业化", "供给侧", "库存", "销量", "排产",
)

_SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "房地产": (
        "房地产", "楼市", "房贷", "地产", "商品房", "城中村", "住房", "购房", "买房",
        "贴息", "首套房", "住房贷款", "按揭补贴", "房贷补贴", "购房补贴",
    ),
    "银行": ("银行", "净息差", "存款利率", "贷款利率", "LPR", "降准"),
    "券商": ("券商", "证券", "资本市场", "IPO", "并购重组", "印花税"),
    "新能源车": ("新能源汽车", "新能源车", "汽车", "以旧换新", "充电桩"),
    "锂电池": ("锂电", "电池", "碳酸锂", "储能"),
    "光伏": ("光伏", "硅料", "硅片", "组件"),
    "半导体": ("半导体", "芯片", "集成电路", "光刻", "先进制程"),
    "人工智能": ("人工智能", "AI", "算力", "大模型", "数据中心"),
    "机器人": ("机器人", "人形机器人", "工业母机", "自动化"),
    "医药": ("医药", "创新药", "医疗器械", "集采", "医保"),
    "消费": ("消费", "白酒", "家电", "零售", "免税", "以旧换新"),
    "军工": ("军工", "国防", "航空航天", "低空经济"),
    "有色金属": ("有色", "铜", "铝", "黄金", "稀土", "小金属"),
    "煤炭": ("煤炭", "动力煤", "焦煤"),
    "石油石化": ("原油", "石油", "天然气", "OPEC"),
    "电力": ("电力", "电网", "绿电", "电价", "核电"),
}

_POSITIVE_KEYWORDS = (
    "支持", "利好", "加快", "扩大", "增长", "提升", "突破", "补贴", "降准", "降息", "回购",
    "增持", "上调", "放宽", "落地", "超预期", "提振", "减税", "贴息", "中标",
)
_NEGATIVE_KEYWORDS = (
    "收紧", "限制", "下滑", "下降", "风险", "处罚", "调查", "制裁", "关税", "亏损", "减持",
    "退市", "暴跌", "不及预期", "停产", "违约", "禁令", "监管趋严",
)

_CENTRAL_POLICY_DOMAINS = (
    "mof.gov.cn",
    "pbc.gov.cn",
    "csrc.gov.cn",
    "ndrc.gov.cn",
    "mohurd.gov.cn",
    "nfra.gov.cn",
)
_AUTHORITATIVE_MEDIA_DOMAINS = ("reuters.com", "chinanews.com.cn", "xinhuanet.com", "people.com.cn")
_LISTING_PAGE_TITLE_PATTERNS = (
    r"^(?:宏观|财经|政策|要闻|新闻)(?:[_｜|·-](?:宏观|财经|中国网|新闻))*$",
    r"^(?:大图新闻|滚动新闻|新闻首页|财经首页|政策首页)$",
)

_EVENT_FINGERPRINT_RULES: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = (
    (
        "housing_interest_subsidy",
        (
            ("住房", "购房", "买房", "房贷", "按揭", "房地产", "首套房", "mortgage", "home purchase"),
            ("贴息", "利息补贴", "按揭补贴", "房贷补贴", "mortgage subsidy", "mortgage subsidies", "interest subsidy"),
        ),
    ),
    ("reserve_requirement_cut", (("央行", "人民银行", "PBOC"), ("降准", "reserve requirement ratio"))),
    ("policy_rate_cut", (("央行", "人民银行", "PBOC"), ("降息", "政策利率", "rate cut"))),
    ("consumer_trade_in", (("以旧换新", "trade-in"), ("补贴", "支持", "subsidy"))),
)


def _contains_keyword(text: str, keyword: str) -> bool:
    """ASCII 缩写按完整单词匹配，避免 AI 命中 daily/said 等普通单词。"""
    if keyword.isascii() and keyword.isalnum():
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None
    return keyword.lower() in text.lower()


def _parse_publish_time(value: object, target_date: date, *, use_realtime: bool) -> datetime | None:
    # 历史复盘用目标日收盘作为解析锚点：允许“09-30 14:20”这类缺年份但
    # 可确定归属的格式；禁止“刚刚/10分钟前/仅时分”，避免拿当前语义回填历史。
    reference = (
        datetime.now(SHANGHAI_TIMEZONE)
        if use_realtime
        else datetime.combine(target_date, time(23, 59, 59), tzinfo=SHANGHAI_TIMEZONE)
    )
    return cast(datetime | None, parse_news_datetime(
        value,
        now=reference,
        allow_relative=use_realtime,
        allow_time_only=use_realtime,
        assume_year=True,
    ))


def filter_news_for_review(
    items: Iterable[NewsSearchItem],
    target_date: date,
    *,
    use_realtime: bool,
    limit: int = 40,
) -> list[NewsSearchItem]:
    """保留复盘日前后两天的解释窗口；事后新闻由 policy timing 显式标记。"""
    earliest = target_date - timedelta(days=2)
    latest = target_date + timedelta(days=2)
    selected: list[NewsSearchItem] = []
    for item in items:
        published_at = _parse_publish_time(item.publish_time, target_date, use_realtime=use_realtime)
        published = published_at.date() if published_at is not None else None
        if published is None:
            continue
        elif published > latest or published < earliest:
            continue
        selected.append(item.model_copy(update={"publish_time": published_at.isoformat(timespec="seconds")}))
        if len(selected) >= limit:
            break
    return selected


def _event_type(text: str) -> str:
    if any(_contains_keyword(text, keyword) for keyword in _POLICY_KEYWORDS):
        return "policy"
    if any(_contains_keyword(text, keyword) for keyword in _MACRO_KEYWORDS):
        return "macro"
    if any(_contains_keyword(text, keyword) for keyword in _GLOBAL_KEYWORDS):
        return "global"
    if any(_contains_keyword(text, keyword) for keyword in _INDUSTRY_KEYWORDS):
        return "industry"
    return "market"


def _direction(text: str) -> str:
    positive = sum(_contains_keyword(text, keyword) for keyword in _POSITIVE_KEYWORDS)
    negative = sum(_contains_keyword(text, keyword) for keyword in _NEGATIVE_KEYWORDS)
    if positive and negative:
        return "mixed"
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def _related_sectors(text: str) -> list[str]:
    return [
        sector
        for sector, keywords in _SECTOR_KEYWORDS.items()
        if any(_contains_keyword(text, keyword) for keyword in keywords)
    ][:6]


def _domain_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def _source_authority(url: str) -> int:
    hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
    if hostname in {"gov.cn", "www.gov.cn"}:
        return 4
    if any(_domain_matches(hostname, domain) for domain in _CENTRAL_POLICY_DOMAINS):
        return 4
    if hostname.endswith(".gov.cn"):
        return 2
    if any(_domain_matches(hostname, domain) for domain in _AUTHORITATIVE_MEDIA_DOMAINS):
        return 1
    return 0


def _is_listing_page(item: NewsSearchItem) -> bool:
    normalized_title = re.sub(r"\s+", "", item.title).strip("_-｜|·")
    if any(re.fullmatch(pattern, normalized_title, flags=re.IGNORECASE) for pattern in _LISTING_PAGE_TITLE_PATTERNS):
        return True
    # 搜索引擎偶尔把频道页当作新闻；同一摘要出现多个独立时间戳，说明不是单一事件。
    dated_entries = re.findall(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?\s+\d{1,2}:\d{2}", item.content)
    return len(dated_entries) >= 2 and len(item.title) <= 16


def _normalized_title(title: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", title.lower())


def _local_policy_scope(text: str) -> str | None:
    matches = re.findall(
        r"([\u4e00-\u9fff]{1,10}(?:省|市|自治区|自治州|区|县))"
        r"(?=.{0,12}(?:出台|发布|实施|推出|住建局|住房和城乡建设))",
        text,
    )
    if not matches:
        return None
    # 排除“我国”等全国性措辞，只保留明确行政区名称。
    return _normalized_title(matches[0])


def _event_fingerprint(text: str) -> str | None:
    for name, required_groups in _EVENT_FINGERPRINT_RULES:
        if not all(any(_contains_keyword(text, keyword) for keyword in group) for group in required_groups):
            continue
        if name == "housing_interest_subsidy" and (scope := _local_policy_scope(text)):
            return f"{name}:{scope}"
        return name
    return None


def _source_label(item: PolicyNewsSnapshotItem) -> str:
    hostname = (urlsplit(item.url).hostname or "").lower().rstrip(".").removeprefix("www.")
    return item.source or hostname


def _merge_corroborating_source(
    primary: PolicyNewsSnapshotItem,
    duplicate: PolicyNewsSnapshotItem,
) -> PolicyNewsSnapshotItem:
    primary_source = _source_label(primary)
    labels = [*primary.corroborating_sources, *duplicate.corroborating_sources]
    duplicate_source = _source_label(duplicate)
    if duplicate_source and duplicate_source != primary_source:
        labels.append(duplicate_source)
    return primary.model_copy(update={"corroborating_sources": list(dict.fromkeys(labels))[:4]})


def classify_policy_news(
    items: Iterable[NewsSearchItem],
    *,
    target_date: date | None = None,
    limit: int = 16,
) -> list[PolicyNewsSnapshotItem]:
    """按政策/宏观/海外/产业相关性排序，并保留可核验来源。"""
    ranked: list[tuple[int, int, PolicyNewsSnapshotItem]] = []
    for index, item in enumerate(items):
        if _is_listing_page(item):
            continue
        text = f"{item.title} {item.content} {item.source}".strip()
        event_type = _event_type(text)
        sectors = _related_sectors(text)
        if event_type == "market" and not sectors:
            continue
        published = parse_news_datetime(item.publish_time)
        timing = "on_date"
        if target_date is not None and published is not None:
            if published.date() < target_date:
                timing = "before"
            elif published.date() > target_date:
                timing = "after"
        score = (
            {
                "policy": 5,
                "macro": 4,
                "global": 3,
                "industry": 2,
                "market": 1,
            }[event_type]
            + min(len(sectors), 3)
            + {"on_date": 2, "before": 1, "after": 0}[timing]
            + _source_authority(item.url)
        )
        ranked.append((
            score,
            -index,
            PolicyNewsSnapshotItem(
                title=item.title,
                content=item.content,
                source=item.source,
                publish_time=item.publish_time,
                url=item.url,
                event_type=event_type,
                direction=_direction(text),
                timing=timing,
                related_sectors=sectors,
            ),
        ))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    selected: list[PolicyNewsSnapshotItem] = []
    event_indices: dict[str, int] = {}
    for _, _, item in ranked:
        text = f"{item.title} {item.content} {item.source} {item.url}"
        keys = {f"title:{_normalized_title(item.title)}"}
        if fingerprint := _event_fingerprint(text):
            keys.add(f"event:{fingerprint}")
        duplicate_index = next((event_indices[key] for key in keys if key in event_indices), None)
        if duplicate_index is not None:
            selected[duplicate_index] = _merge_corroborating_source(selected[duplicate_index], item)
            continue
        if len(selected) >= limit:
            continue
        selected_index = len(selected)
        selected.append(item)
        for key in keys:
            event_indices[key] = selected_index
    return selected
