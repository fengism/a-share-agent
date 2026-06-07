import asyncio
import logging
import re
from collections import Counter
import pandas as pd

from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.services.analysis.news import get_stock_news
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking
from app.utils.data_clean import safe_float, safe_int
from app.utils.symbol_utils import normalize_code
from app.utils.news_utils import filter_recent_news_items


logger = logging.getLogger(__name__)

MAX_POST_NUM = 10
_BULLISH_TERMS = ["看多", "看涨", "利好", "买入", "加仓", "反弹", "突破", "主升", "低吸", "看好", "上涨", "拉升"]
_BEARISH_TERMS = ["看空", "看跌", "利空", "卖出", "减仓", "下跌", "破位", "套牢", "暴跌", "回调", "风险", "跌停"]
_STOPWORDS = {
    "今天", "明天", "这个", "那个", "感觉", "还是", "真的", "可能", "就是", "一个", "没有", "什么", "我们", "你们", "他们",
    "市场", "情绪", "股票", "公司", "现在", "可以", "因为", "亿元", "万元", "同比增长", "同比增加", "同比上升", "同比下降",
    "营业收入", "归母净利润", "净利润", "一季报", "年报", "半年报", "季报", "发布公告", "实现营业", "实现净利润", "None",
    "贵州茅台", "将召开线上业绩说明会", "召开线上业绩说明会", "召开业绩说明会", "邀您观看", "主场", "有什么好怕的", "江东子弟何在",
    "同比", "公告称", "较去年", "第一季度", "董事", "代总经理", "拟出席", "线上业绩说明会", "出席",
}


def _normalize_text_for_compare(text: str) -> str:
    """Normalize text for duplicate comparison by stripping punctuation and whitespace.

    Param:
        text: raw text to normalize
    Return:
        lowercased text with all whitespace and common punctuation removed
    """
    return re.sub(r"[\s\"“”'‘’。！？!?,，：:；;（）()\-]+", "", str(text or "")).strip().lower()


def _clean_retail_post(text: str) -> str:
    """Clean raw retail post text by removing boilerplate phrases and trailing noise.

    Param:
        text: raw post text
    Return:
        cleaned post text
    """
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"邀您观看[:：]?", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"(召开线上业绩说明会|召开业绩说明会|拟出席|董事、代总经理.*)$", "", cleaned)
    return cleaned.strip("。 .")


def _is_low_signal_post(text: str) -> bool:
    """Determine whether a post is low-signal and should be filtered out.

    Param:
        text: cleaned post text
    Return:
        True if the post is too short, low-value, or boilerplate
    """
    stripped = str(text or "").strip()
    if not stripped:
        return True
    if len(stripped) < 12:
        return True
    if stripped.endswith(("将", "拟", "召开", "说明会")):
        return True
    low_signal_patterns = [
        r"业绩说明会",
        r"投资者交流",
        r"直播",
        r"欢迎收看",
        r"点击查看",
        r"转发微博",
    ]
    return any(re.search(pattern, stripped) for pattern in low_signal_patterns)


def _aggregate_retail_sentiment(posts: list[dict]) -> dict:
    """Aggregate cleaned retail posts into a sentiment summary with bullish/bearish ratios.

    Param:
        posts: list of post dicts with text, author, and publish_time
    Return:
        dict with score, post_count, bullish_ratio, bearish_ratio, sample_posts, and summary
    """
    cleaned_posts = []
    seen_texts = set()
    term_counter = Counter()

    for post in posts:
        raw_text = str(post.get("text") or "")
        text = _clean_retail_post(raw_text)
        if _is_low_signal_post(text):
            continue
        normalized = _normalize_text_for_compare(text)
        if not normalized or normalized in seen_texts:
            continue
        seen_texts.add(normalized)

        tokens = re.findall(r"[一-鿿A-Za-z0-9]+", text)
        filtered_tokens = [token for token in tokens if token not in _STOPWORDS and len(token) > 1]
        term_counter.update(filtered_tokens)
        cleaned_posts.append(
            {
                "text": text,
                "author": post.get("author"),
                "publish_time": post.get("publish_time"),
            }
        )

    if not cleaned_posts:
        return {
            "score": None,
            "post_count": 0,
            "bullish_ratio": None,
            "bearish_ratio": None,
            "sample_posts": [],
            "summary": "暂无散户讨论样本",
        }

    bullish_count = 0
    bearish_count = 0
    for post in cleaned_posts:
        bullish_hits = sum(term in post["text"] for term in _BULLISH_TERMS)
        bearish_hits = sum(term in post["text"] for term in _BEARISH_TERMS)
        if bullish_hits > bearish_hits:
            bullish_count += 1
        elif bearish_hits > bullish_hits:
            bearish_count += 1

    total_posts = len(cleaned_posts)
    bullish_ratio = round(bullish_count / total_posts, 3) if total_posts else None
    bearish_ratio = round(bearish_count / total_posts, 3) if total_posts else None
    sentiment_balance = bullish_count - bearish_count
    score = round(max(0, min(100, 50 + sentiment_balance * 10)), 1)
    if bullish_count == bearish_count:
        summary = "散户讨论情绪中性，观点分歧较大"
    elif bullish_count > bearish_count:
        summary = "散户讨论偏多，正向观点占优"
    else:
        summary = "散户讨论偏空，谨慎情绪更强"

    sample_posts = []
    for post in cleaned_posts[:MAX_POST_NUM]:
        text = post["text"][:180] + "..." if len(post["text"]) > 180 else post["text"]
        sample_posts.append(
            {
                "text": text,
                "author": post["author"],
                "publish_time": post["publish_time"],
            }
        )

    return {
        "score": score,
        "post_count": total_posts,
        "bullish_ratio": bullish_ratio,
        "bearish_ratio": bearish_ratio,
        "sample_posts": sample_posts,
        "summary": summary,
    }


def fetch_hot_detail_em(symbol: str) -> pd.DataFrame:
    """Fetch hot-rank detail for a stock symbol from the akshare provider.

    Param:
        symbol: prefixed stock symbol, e.g. "SZ000001"
    Return:
        DataFrame of hot-rank detail rows
    """
    return _akshare_provider.fetch_hot_rank_detail(symbol)



async def get_stock_sentiment(code: str) -> dict:
    """Get aggregated stock sentiment data (heat score, rank, news count) with daily cache.

    Param:
        code: 6-digit stock code
    Return:
        dict with code, heat_score, hot_rank, and news_count
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("sentiment", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result: dict = {
        "code": sym.raw,
        "heat_score": None,
        "hot_rank": None,
        "news_count": 0,
    }

    try:
        df = await call_blocking(fetch_hot_detail_em, symbol=sym.prefixed_upper)
        if len(df) > 0:
            row = df.iloc[-1]
            result["hot_rank"] = safe_int(row.get("排名"))
            new_fans = safe_float(row.get("新晋粉丝"))
            loyal_fans = safe_float(row.get("铁杆粉丝"))
            if new_fans is not None and loyal_fans is not None:
                result["heat_score"] = round((new_fans + loyal_fans) * 100, 1)
    except Exception:
        logger.info(f"个股热度明细数据获取失败: {sym.raw}")
    try:
        news = await get_stock_news(code)
        result["news_count"] = len(news)
    except Exception as exc:
        logger.info("新闻数据获取失败: code=%s, error=%s", code, exc)

    cache.set(cache_key, result, ttl=600)
    return result



async def get_retail_sentiment(code: str) -> dict:
    """Get aggregated retail-sentiment metrics from Eastmoney guba posts with daily cache.

    Param:
        code: 6-digit stock code
    Return:
        dict with score, post_count, bullish_ratio, bearish_ratio, sample_posts, summary, and guba_post_count
    """
    sym = normalize_code(code)
    cache_key = dated_cache_key("retail_sentiment", sym.raw)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {
        "code": sym.raw,
        "score": None,
        "post_count": 0,
        "bullish_ratio": None,
        "bearish_ratio": None,
        "sample_posts": [],
        "summary": "暂无散户讨论样本",
        "guba_post_count": 0,
    }

    try:
        guba_posts = await call_blocking(_eastmoney_provider.fetch_stock_guba_posts, code)
        result["guba_post_count"] = len(guba_posts)
        retail_posts = []
        for item in guba_posts:
            title = str(getattr(item, "title", "") or "").strip()
            content = str(getattr(item, "content", "") or "").strip()
            normalized_title = _normalize_text_for_compare(title)
            normalized_content = _normalize_text_for_compare(content)
            if normalized_content and normalized_title and normalized_content == normalized_title:
                merged = title or content
            elif normalized_content and normalized_title and normalized_content.startswith(normalized_title):
                merged = content
            else:
                merged = "。".join(part for part in [title, content] if part and part.lower() != "none")
            merged = merged.strip()
            if merged and len(merged) <= 1200:
                retail_posts.append(
                    {
                        "text": merged,
                        "author": getattr(item, "author", None),
                        "publish_time": getattr(item, "publish_time", None),
                    }
                )
        retail_posts = filter_recent_news_items(retail_posts)
        result["guba_post_count"] = len(retail_posts)
        aggregated = _aggregate_retail_sentiment(retail_posts)
        result.update(aggregated)
    except Exception as e:
        logger.info(f"散户情绪样本获取失败: {sym.raw}, error={e}")

    cache.set(cache_key, result, ttl=600)
    return result


if __name__ == "__main__":
    result = asyncio.run(get_retail_sentiment("603228"))
    print(result)