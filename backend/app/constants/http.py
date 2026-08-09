import random

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Thunder Client (https://www.thunderclient.com)",
]


def random_user_agent() -> str:
    """从列表中随机选择一个 User-Agent 字符串。

    Return:
        随机选取的 User-Agent 字符串。
    """
    return random.choice(USER_AGENTS)


def build_headers(base: dict[str, str]) -> dict[str, str]:
    """在给定的 headers 字典基础上添加随机 User-Agent。

    Param:
        base: 基础 headers 字典。
    Return:
        复制后的 headers 字典，其中 User-Agent 已被随机替换。
    """
    headers = dict(base)
    headers["User-Agent"] = random_user_agent()
    return headers

EASTMONEY_HEADERS = build_headers({
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Connection": "keep-alive",
})

THS_HEADERS = build_headers({
    "Host": "dq.10jqka.com.cn",
    "Referer": "http://q.10jqka.com.cn/",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
})

CLS_HEADERS = build_headers({
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.cls.cn/telegraph",
    "Origin": "https://www.cls.cn",
})

SINA_FINANCE_HEADERS = build_headers({
    "Referer": "https://finance.sina.com.cn",
})

COMMON_HEADERS = build_headers({
    "Accept": "*/*",
})

TENCENT_FINANCE_HEADERS = build_headers({
    "Accept": "*/*",
    "referer": "https://gu.qq.com/",
})


BD_HEADERS = build_headers({
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://finance.baidu.com",
    "Origin": "https://finance.baidu.com",
})


BD_HEADERS_WITH_COOKIE =build_headers({
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://finance.baidu.com",
    "Origin": "https://finance.baidu.com",
})
