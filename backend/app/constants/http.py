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

EASTMONEY_COOKIE = "st_nvi=g4m0d6etwkGEZiGDu5SnRc09b; emshistory=%5B%22%E6%99%AF%E6%97%BA%E7%94%B5%E5%AD%90%22%5D; qgqp_b_id=a09dcdfd4160d07a4be8aefbea69d195; st_si=92209040856734; nid18=054d22a620ef5d713ccec6748a620265; nid18_create_time=1780586118901; gviem=zlK3j9JLe3GWBtoNPK9Jp644a; gviem_create_time=1780586118901; wsc_checkuser_ok=1; fullscreengg=1; fullscreengg2=1; st_asi=delete; st_pvi=42924896055142; st_sp=2026-02-26%2022%3A59%3A18; st_inirUrl=https%3A%2F%2Fcn.bing.com%2F; st_sn=27; st_psi=20260604235743304-113200302671-1319660370"

EASTMONEY_HEADERS = build_headers({
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Connection": "keep-alive",
    "cookie": EASTMONEY_COOKIE,
})

EASTMONEY_STATICS_HEADERS = build_headers({
    "Accept": "*/*",
    "Cookie": EASTMONEY_COOKIE,
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


BD_HEADERS = build_headers({
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://finance.baidu.com",
    "Origin": "https://finance.baidu.com",
    "cookie": "BAIDUID_BFESS=DB1FF824C51A8A7EC1CB5709787F55F3:FG=1; BIDUPSID=DB1FF824C51A8A7EC1CB5709787F55F3; PSTM=1748161798; __bid_n=199d43408362656aa984d8; BAIDU_WISE_UID=wapp_1763293519697_505; BDB2BVID=a7974a875477c5d141a5adf3fba626cb; ZFY=ltArLceypK4:Bj7kR07bg0RehWyV21HlnAvq8O:BMgIlg:C; H_PS_PSSID=63140_67602_67862_68166_69007_69203_69295_69586_69766_69796_69844_69905_69899_69962_70003_70044_70036_70117_70152_70161_70225_70192_70300_70280_70321_70142_69924_70356_70426_70411_70467_70474_70471_70486_70368_70564_70611; H_WISE_SIDS=63140_67602_67862_68166_69007_69203_69295_69586_69766_69796_69844_69905_69899_69962_70003_70044_70036_70117_70152_70161_70225_70192_70280_70321_70142_69924_70356_70426_70411_70467_70474_70471_70486_70368_70564_70611; ab_sr=1.0.1_OWIxYTVlZjA5MzJkZmQzYzQ5ZTQ3ODEwYzI4MGUwOWRjMDRiMzllOWExZjliZTc1OTM3Y2M4NTM3Y2JhNDQ5MjZjZTBhZTc3ODRjN2YzMWNhMDc1OTcxM2I0NzIwYzcyNGY2YTk0MmM4Yzk4ODAxYWM5MjVlZGE0ODU1MWNlODRiOWMyZDg2YTE2MjE3OWFkMTk1NTU0ZjliNGZhN2ZkMQ==; ppfuid=5c47b98ba2fe6fdeebd7c26aed483434"
})


BD_HEADERS_WITH_COOKIE =build_headers({
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://finance.baidu.com",
    "Origin": "https://finance.baidu.com",
    "cookie": "BAIDUID_BFESS=DB1FF824C51A8A7EC1CB5709787F55F3:FG=1; BIDUPSID=DB1FF824C51A8A7EC1CB5709787F55F3; PSTM=1748161798; __bid_n=199d43408362656aa984d8; BAIDU_WISE_UID=wapp_1763293519697_505; BDB2BVID=a7974a875477c5d141a5adf3fba626cb; ZFY=ltArLceypK4:Bj7kR07bg0RehWyV21HlnAvq8O:BMgIlg:C; H_PS_PSSID=63140_67602_67862_68166_69007_69203_69295_69586_69766_69796_69844_69905_69899_69962_70003_70044_70036_70117_70152_70161_70225_70192_70300_70280_70321_70142_69924_70356_70426_70411_70467_70474_70471_70486_70368_70564_70611; H_WISE_SIDS=63140_67602_67862_68166_69007_69203_69295_69586_69766_69796_69844_69905_69899_69962_70003_70044_70036_70117_70152_70161_70225_70192_70280_70321_70142_69924_70356_70426_70411_70467_70474_70471_70486_70368_70564_70611; ab_sr=1.0.1_OWIxYTVlZjA5MzJkZmQzYzQ5ZTQ3ODEwYzI4MGUwOWRjMDRiMzllOWExZjliZTc1OTM3Y2M4NTM3Y2JhNDQ5MjZjZTBhZTc3ODRjN2YzMWNhMDc1OTcxM2I0NzIwYzcyNGY2YTk0MmM4Yzk4ODAxYWM5MjVlZGE0ODU1MWNlODRiOWMyZDg2YTE2MjE3OWFkMTk1NTU0ZjliNGZhN2ZkMQ==; ppfuid=5c47b98ba2fe6fdeebd7c26aed483434"
})
