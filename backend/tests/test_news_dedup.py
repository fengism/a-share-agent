from __future__ import annotations

from app.core.news import clean_headline, dedupe_news_items


def test_clean_headline_removes_platform_prefixes_and_suffixes() -> None:
    # 常见平台方头括号前缀
    assert clean_headline("【快讯】央行开展1000亿元逆回购操作") == "央行开展1000亿元逆回购操作"
    assert clean_headline("【财联社4月15日电】工信部部署新型工业化工作") == "工信部部署新型工业化工作"
    assert clean_headline("[最新播报] 国际金价突破2400美元") == "国际金价突破2400美元"

    # 通讯社电讯前缀
    assert clean_headline("新华社北京4月15日电 商务部召开例行新闻发布会") == "商务部召开例行新闻发布会"
    assert clean_headline("财联社4月15日电，国家统计局发布最新经济数据") == "国家统计局发布最新经济数据"

    # 末尾媒体括号后缀
    assert clean_headline("财政部发行超长期特别国债（新浪财经）") == "财政部发行超长期特别国债"
    assert clean_headline("华为发布新一代AI芯片解决方案(证券时报网)") == "华为发布新一代AI芯片解决方案"
    assert clean_headline("中央汇金扩大ETF增持范围（来源：中国证券报）") == "中央汇金扩大ETF增持范围"

    # 末尾破折号后缀
    assert clean_headline("A股三大指数集体收涨 - 东方财富网") == "A股三大指数集体收涨"
    assert clean_headline("美联储暗示年内降息路径——华尔街见闻") == "美联储暗示年内降息路径"


def test_dedupe_news_items_exact_canonical() -> None:
    items = [
        {"title": "【快讯】央行开展1000亿元逆回购操作", "source": "东方财富", "publish_time": "2026-04-15 09:15:00"},
        {"title": "【财联社4月15日电】央行开展1000亿元逆回购操作", "source": "财联社", "publish_time": "2026-04-15 09:15:02"},
        {"title": "央行开展1000亿元逆回购操作（新浪财经）", "source": "新浪财经", "publish_time": "2026-04-15 09:15:10"},
        {"title": "央行开展1000亿元逆回购操作 - 华尔街见闻", "source": "华尔街见闻", "publish_time": "2026-04-15 09:15:15"},
        # 不同的新闻
        {"title": "国家发改委部署大规模设备更新", "source": "新华社", "publish_time": "2026-04-15 09:20:00"},
    ]

    deduped = dedupe_news_items(items)
    # 前 4 条属于同一事件不同媒体转载，应该仅保留第 1 条
    assert len(deduped) == 2
    assert deduped[0]["source"] == "东方财富"
    assert deduped[1]["title"] == "国家发改委部署大规模设备更新"


def test_dedupe_news_items_fuzzy_near_duplicates() -> None:
    items = [
        {"title": "央行开展1000亿元7天期逆回购操作", "source": "财联社"},
        {"title": "央行今日开展1000亿元逆回购操作", "source": "东方财富"},
        {"title": "美股全线收跌纳指下挫逾1%", "source": "华尔街见闻"},
    ]

    deduped = dedupe_news_items(items, fuzzy=True, sim_threshold=0.75)
    # 央行逆回购同质报道被合并
    assert len(deduped) == 2
    assert deduped[0]["title"] == "央行开展1000亿元7天期逆回购操作"
    assert deduped[1]["title"] == "美股全线收跌纳指下挫逾1%"
