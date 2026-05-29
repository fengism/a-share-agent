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
    return random.choice(USER_AGENTS)


def build_headers(base: dict[str, str]) -> dict[str, str]:
    headers = dict(base)
    headers["User-Agent"] = random_user_agent()
    return headers

EASTMONEY_HEADERS = build_headers({
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Connection": "keep-alive",
    "cookie": "qgqp_b_id=b17e651f9bca7585f6e2e8e0ba4e91ee; st_nvi=6hHDz8pD6iGiNwad7KCce0f8c; nid18=0ea78d8b7ecb53018008ec947866af1f; nid18_create_time=1772092956669; gviem=7nlg-6Vl8Sv-h6ioGS4_j11e1; gviem_create_time=1772092956669; emshistory=%5B%22600337%22%2C%22%E6%9D%A5%E4%BC%8A%E4%BB%BD%22%2C%22600519%22%2C%2260519%22%5D; quote_lt=1; websitepoptg_api_time=1778392585412; st_si=62900329194795; st_asi=delete; fullscreengg=1; fullscreengg2=1; wsc_checkuser_ok=1; st_pvi=52494799947571; st_sp=2025-07-25%2015%3A41%3A51; st_inirUrl=https%3A%2F%2Fwww.google.com.hk%2F; st_sn=31; st_psi=20260510224114732-113200313002-9432233957",
})

EASTMONEY_STATICS_HEADERS = build_headers({
    "Accept": "*/*",
    "Cookie": "qgqp_b_id=b17e651f9bca7585f6e2e8e0ba4e91ee; st_nvi=6hHDz8pD6iGiNwad7KCce0f8c; nid18=0ea78d8b7ecb53018008ec947866af1f; nid18_create_time=1772092956669; gviem=7nlg-6Vl8Sv-h6ioGS4_j11e1; gviem_create_time=1772092956669; emshistory=%5B%22600337%22%2C%22%E6%9D%A5%E4%BC%8A%E4%BB%BD%22%2C%22600519%22%2C%2260519%22%5D; quote_lt=1; websitepoptg_api_time=1778392585412; st_si=62900329194795; st_asi=delete; fullscreengg=1; fullscreengg2=1; wsc_checkuser_ok=1; st_pvi=52494799947571; st_sp=2025-07-25%2015%3A41%3A51; st_inirUrl=https%3A%2F%2Fwww.google.com.hk%2F; st_sn=31; st_psi=20260510224114732-113200313002-9432233957",
})

THS_HEADERS = build_headers({
    "Host": "dq.10jqka.com.cn",
    "Referer": "http://q.10jqka.com.cn/",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "cookie": "ga=GA1.1.535211331.1772422747; __utma=156575163.535211331.1772422747.1773140225.1773140225.1; __utmz=156575163.1773140225.1.1.utmcsr=news.10jqka.com.cn|utmccn=(referral)|utmcmd=referral|utmcct=/; Hm_lvt_722143063e4892925903024537075d0d=1777198753; Hm_lvt_929f8b362150b1f77b477230541dbbc2=1777198753; userid=ths_gu_94685f0a012f67aa15af7fa31e7a5e7b; Hm_lvt_69929b9dce4c22a060bd22d703b2a280=1777198705,1778349670; Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1777198728,1778349682; v=A4Dsi4_e_bzFFYG400T5GggiVwVXCWaQBu241_oRTBsudS47ohk0Y1b9iEVJ; _ga_H2RK0R0681=GS2.1.s1778349671$o6$g1$t1778350411$j58$l0$h0",
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

