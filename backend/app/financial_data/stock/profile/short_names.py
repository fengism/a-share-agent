"""自动派生 A 股简称与拼音首字母索引。

索引从完整股票名映射派生，新增股票或改名会自动跟随。词缀候选不再手工维护，
而是自动统计：

- 所有 2 字前缀/后缀
- 所有 3-4 字前缀，且在名称映射中出现 >= 2 次

需要维护的只有通用语言数据（地名、行业词、常见词），不是股票清单本身。

检测分三级：

- 完整名 / A-B 归一 / 拼音首字母：高置信
- 派生简称：需要同时出现股票语境词才判定，避免把“友好往来”当股票
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Collection

# 地名/限定词：不作为简称候选。
_PLACE_WORDS: tuple[str, ...] = tuple("""
中国 北京 上海 天津 重庆 河北 山西 辽宁 吉林 黑龙江 江苏 浙江 安徽 福建 江西 山东 河南 湖北
湖南 广东 广西 海南 四川 贵州 云南 陕西 甘肃 青海 宁夏 新疆 西藏 内蒙古 内蒙 香港 澳门 台湾
深圳 广州 杭州 南京 武汉 成都 西安 沈阳 大连 青岛 宁波 厦门 苏州 无锡 常州 南通 徐州 济南 烟台
潍坊 淄博 临沂 郑州 长沙 合肥 福州 南昌 太原 石家庄 哈尔滨 长春 昆明 贵阳 南宁 兰州 银川 西宁
乌鲁木齐 呼和浩特 拉萨 海口 三亚 佛山 东莞 珠海 中山 惠州 江门 绍兴 嘉兴 台州 金华 温州 泉州
湖州 扬州 泰州 镇江 盐城 淮安 连云港 宿迁 保定 唐山 廊坊 秦皇岛 邯郸 沧州 科大 中科 清华 北大
""".split())

# 行业/法律词：不作为简称候选。
_INDUSTRY_WORDS: tuple[str, ...] = tuple("""
股份 集团 控股 科技 电子 医药 生物 银行 证券 保险 基金 信托 能源 电力 汽车 重工 机械 材料 化工
环保 通信 网络 软件 数据 智能 信息 高科 新能 锂业 矿业 国际 发展 实业 工业 水泥 钢铁 有色 黄金
传媒 文化 旅游 地产 置业 建设 工程 装备 精密 电源 光电 激光 医疗 制药 食品 乳业 酒业 家电 家居
物流 航空 机场 港口 高速 铁路 电气 仪表 自控 半导体 微电子 电池 新材 新材料 石墨 碳素 纸业 包装
印刷 农业 牧业 渔业 林业 种业 化肥 农药 饲料 养殖 纺织 服装 珠宝 稀土 磁材 管道 阀门 轴承 模具
特钢 钢管 玻璃 陶瓷 涂料 染料 树脂 橡胶 塑料 化纤 粘胶 造纸 船舶 重装 钢构 装饰 园林 燃气 水务
热力 酒店 商业 百货 超市 零售 贸易 快递 出版 教育 培训 游戏 影视 娱乐 广告 电脑 数码 通讯 云计算
机器人 无人机 卫星 导航 测绘 地理 威视 智造 智控 动力 重机 康德 绿能 光子 量子 智能
""".split())

# 通用词：不作为简称候选。
_COMMON_WORDS: tuple[str, ...] = tuple("""
友好 人民 健康 快乐 幸福 美好 人人 家家 天天 阳光 东方 恒生 金山 移动 联通 电信 中环 中华
中信 招商 平安 中国 中心 中兴 大学 中学 小学 医院 期货 石油 石化 煤炭 建筑 建材 黄金 白银
板块 行业 题材 大盘 指数 成交额 市场 宏观 汇率 通胀 通缩 主线 风格 成分股 股票 个股 股价
估值 财报 财务 营收 净利润 风险 止损 仓位 目标价 支撑位 压力位 走势 港股 恒指 港元 新闻 资讯
公告 研报 白皮书 选股 筛选 策略 回测 计算 系统 平台 服务 第一 自然 饮食 矿机 汽配 煤电 通用
大众 公用 交通 生活 时尚 现代 联合 环球 世界 亚洲 欧洲 美洲 华夏 中央 国家 东北 华北 华东
华南 西部 南方 北方 长江 黄河 泰山 黄山 峨眉山 新能源 大数据 人工智能 互联网 物联网 区块链
元宇宙 碳中和 光伏 储能 锂电池 白酒 军工 券商 基建 消费 成长 价值 周期 龙头 概念 中字头
半导 标准 远程 助手 变速 清新 朝阳 梅花 飞天 财富 神州 麒麟
""".split())

_GENERIC_WORDS: frozenset[str] = (
    frozenset(_PLACE_WORDS)
    | frozenset(_INDUSTRY_WORDS)
    | frozenset(_COMMON_WORDS)
)

# 规则无法安全派生、但极常用的真简称。
_EXCEPTION_ALIASES: frozenset[str] = frozenset({
    "招行", "工行", "建行", "农行", "中行", "交行", "宁王",
})

# 拼音首字母命中也要排除这些英文常见词，避免英文句子误判。
_PINYIN_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "you", "are", "but", "not", "all", "can", "has", "new", "one",
    "out", "see", "now", "how", "why", "who", "use", "get", "make", "like", "time",
    "data", "news", "info", "test", "open", "high", "low", "buy", "sell", "fund",
    "bank", "hold", "risk", "true", "false", "null", "none", "http", "html", "json",
    "api", "llm", "gpt", "pdf", "url", "app", "web", "macd", "rsi", "kdj", "pe", "pb",
})

# 出现这些词才把“派生简称”当成股票标的。
_STOCK_CONTEXT_KEYWORDS: tuple[str, ...] = tuple("""
股票 个股 股价 估值 市值 市盈率 市净率 财报 财务 roe 营收 净利润 主营 技术面 基本面 k线
macd rsi kdj 走势 新闻 公告 舆情 情绪 风险 止损 仓位 目标价 支撑位 压力位 怎么样 如何
分析 看看 对比 港股 恒指 恒生 h股 分红 回购 增持 减持 龙虎榜 涨跌 涨幅 跌幅 收盘 开盘
""".split())

_ASCII_TOKEN_RE = re.compile(r"[A-Za-z]{3,}")


def normalize_name(name: str) -> str:
    """NFKC 归一并去掉空格，兼容全角字母与代码。"""
    return unicodedata.normalize("NFKC", str(name)).replace(" ", "").strip()


def build_short_name_index(
    names: Collection[str],
    *,
    include_exceptions: bool = True,
) -> frozenset[str]:
    """从完整名自动统计词缀，生成 2-4 字简称索引。"""
    normalized = [normalize_name(name) for name in names]
    full_names = set(normalized)
    counts: Counter[str] = Counter()
    for name in normalized:
        length = len(name)
        for size in (2, 3, 4):
            if length <= size:
                continue
            counts[name[:size]] += 1
            if size == 2:
                counts[name[-size:]] += 1
    aliases = {
        gram
        for gram, count in counts.items()
        if len(gram) >= 2
        and gram not in _GENERIC_WORDS
        and gram not in full_names
        and (len(gram) == 2 or count >= 2)
    }
    if include_exceptions:
        aliases |= _EXCEPTION_ALIASES
    return frozenset(aliases)


def is_generic_word(value: str) -> bool:
    """是否属于不应作为简称的通用词。"""
    return normalize_name(value) in _GENERIC_WORDS


def build_pinyin_index(names: Collection[str]) -> frozenset[str]:
    """从完整名派生拼音首字母索引（长度 >= 3）。"""
    try:
        from pypinyin import lazy_pinyin
    except ImportError:  # pragma: no cover - pypinyin 是声明依赖
        return frozenset()
    initials: set[str] = set()
    for raw in names:
        name = normalize_name(raw)
        if not any("\u4e00" <= char <= "\u9fff" for char in name):
            continue
        token = "".join(item[0][0] for item in lazy_pinyin(name)).lower()
        if len(token) >= 3 and token not in _PINYIN_STOPWORDS:
            initials.add(token)
    return frozenset(initials)


def extract_pinyin_tokens(message: str) -> tuple[str, ...]:
    """提取消息中的 ASCII 字母词，供拼音首字母匹配。"""
    return tuple(
        token.lower()
        for token in _ASCII_TOKEN_RE.findall(message)
        if token.lower() not in _PINYIN_STOPWORDS
    )


def has_stock_context(message: str) -> bool:
    """消息是否包含股票语境词（用于给派生简称加门控）。"""
    folded = message.casefold()
    return any(keyword in folded for keyword in _STOCK_CONTEXT_KEYWORDS)


__all__ = [
    "build_pinyin_index",
    "build_short_name_index",
    "extract_pinyin_tokens",
    "has_stock_context",
    "is_generic_word",
    "normalize_name",
]
