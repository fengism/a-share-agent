import json
import logging
import re
import time

import pandas as pd
from bs4 import BeautifulSoup

from app.core.market import contains_stock_reference
from app.domain.news import NewsSearchItem

logger = logging.getLogger(__name__)

_EM_TAG_PATTERNS = [
    (r"\(<em>", ""),
    (r"</em>\)", ""),
    (r"<em>", ""),
    (r"</em>", ""),
]


def _strip_em_tags(series: "pd.Series") -> "pd.Series":
    """清除 DataFrame 列中的 <em> 高亮标签。

    Param:
        series: pandas Series 包含 HTML 标记的文本列
    Return:
        清除标签后的 Series
    """
    for pattern, replacement in _EM_TAG_PATTERNS:
        series = series.str.replace(pattern, replacement, regex=True)
    return series


class NewsMixin:
    """东方财富 news 数据接口。"""

    def fetch_market_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富财经新闻（中国+国际+导读）。

        Param:
            code: 可选，股票代码，用于过滤相关新闻
            code_name: 可选，股票名称，用于过滤相关新闻
        Return:
            list[NewsSearchItem]: 新闻列表
        """
        news_ids: list[str] = []
        all_news: list[NewsSearchItem] = []
        for column, label in [("350", "中国新闻"), ("351", "国际新闻"), ("366", "导读新闻")]:
            try:
                items, news_ids = self._fetch_finance_news(
                    column=column, news_ids=news_ids, code=code, code_name=code_name,
                )
                all_news.extend(items)
            except Exception as e:
                logger.warning(f"东方财富{label}获取失败: {e}")
        return all_news

    def _fetch_finance_news(self, column: str = "", news_ids: list[str] | None = None,
                            code: str = "", code_name: str = "") -> tuple[list[NewsSearchItem], list[str]]:
        """获取东方财富单分类新闻。

        Param:
            column: 新闻分类 ID（如 "350" 中国新闻、"351" 国际新闻、"366" 导读新闻）
            news_ids: 已有的新闻 ID 列表，用于去重
            code: 可选，股票代码，用于过滤相关新闻
            code_name: 可选，股票名称，用于过滤相关新闻
        Return:
            tuple[list[NewsSearchItem], list[str]]:
                - list: 新闻列表
                - list: 更新后的新闻 ID 列表（含本次新增）
        """
        if news_ids is None:
            news_ids = []
        trace = str(int(time.time() * 1000))
        url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
        params = {
            "client": "web", "biz": "web_news_col", "column": str(column),
            "order": "1", "needInteractData": "0", "page_index": "1", "page_size": "20",
            "req_trace": trace,
            "fields": "code,showTime,title,mediaName,summary,image,url,uniqueUrl,Np_dst",
            "types": "1,20", "_": trace,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuaixun.eastmoney.com/",
        }
        r = self.em_get_response(url, params=params, headers=headers, timeout=10)
        d = r.json()
        rows: list[NewsSearchItem] = []
        for item in d.get("data", {}).get("list", []):
            title = str(item.get("title") or "").strip()
            content = str(item.get("summary") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            news_id = item.get("code", title)
            if news_id in news_ids:
                continue
            news_ids.append(news_id)
            rows.append(NewsSearchItem(
                title=title, content=content,
                publish_time=item.get("showTime", ""),
                url=item.get("url", ""),
                source="东方财富",
                author=item.get("mediaName", ""),
                read_count=int(item.get("read_count", 0)),
                comment_count=int(item.get("comment_count", 0)),
            ))
        return rows, news_ids

    def fetch_stock_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富个股新闻（column=107）。

        Param:
            code: 股票代码
            code_name: 股票名称，用于过滤相关新闻
        Return:
            list[NewsSearchItem]: 新闻列表
        """
        url = "http://search-api-web.eastmoney.com/search/jsonp"
        inner_param = {
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": 10,
                    "preTag": "<em>",
                    "postTag": "</em>",
                }
            },
        }
        params = {
            "cb": "jQuery35101792940631092459_1764599530165",
            "param": json.dumps(inner_param, ensure_ascii=False),  # 保留中文,
            "_": "1764599530176",
        }
        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
            "cache-control": "no-cache",
            "connection": "keep-alive",
            **({"cookie": self.eastmoney_headers["cookie"]} if "cookie" in self.eastmoney_headers else {}),
            "host": "search-api-web.eastmoney.com",
            "pragma": "no-cache",
            "referer": f"https://so.eastmoney.com/news/s?keyword={code}",
            "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "script",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        }
        r = self.em_get_response(url, params=params, headers=headers, timeout=10)
        data_text = r.text
        data_json = self._parse_json_from_text(data_text, "个股新闻接口返回格式异常")
        temp_df = pd.DataFrame(data_json.get("result", {}).get("cmsArticleWebOld") or [])
        if temp_df.empty:
            return []
        temp_df["url"] = "http://finance.eastmoney.com/a/" + temp_df["code"] + ".html"
        temp_df.rename(
            columns={
                "date": "publish_time",
                "mediaName": "source",
                "code": "-",
                "title": "title",
                "content": "content",
                "url": "url",
                "image": "-",
            },
            inplace=True,
        )
        temp_df["code"] = code
        temp_df = temp_df[
            [
                "code",
                "title",
                "content",
                "publish_time",
                "source",
                "url",
            ]
        ]
        temp_df["title"] = _strip_em_tags(temp_df["title"])
        temp_df["content"] = _strip_em_tags(temp_df["content"])
        # 必须走 regex=False 的字面量替换：pandas 3 的字符串 dtype 底层是 pyarrow，
        # 其正则引擎（RE2）不支持 ``\u3000`` 这类转义，会抛
        # ArrowInvalid: Invalid regular expression: invalid escape sequence: \u。
        temp_df["content"] = temp_df["content"].str.replace("\u3000", "", regex=False)
        temp_df["content"] = temp_df["content"].str.replace("\r\n", " ", regex=False)
        results: list[NewsSearchItem] = []
        if temp_df is not None and not temp_df.empty:
            for _, row in temp_df.head(20).iterrows():
                results.append(
                    NewsSearchItem(
                        title=str(row.get("title", "")),
                        content=str(row.get("content", "")),
                        source=str(row.get("source", "")),
                        publish_time=str(row.get("publish_time", "")),
                        url=str(row.get("url", "")),
                        author=str(row.get("author", "")),
                        read_count=int(row.get("read", 0)),
                        comment_count=int(row.get("comment", 0)),
                    )
                )
        return results

    def fetch_market_kuaixun(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富 7x24 快讯。

        Param:
            code: 可选，股票代码，用于过滤相关新闻
            code_name: 可选，股票名称，用于过滤相关新闻
        Return:
            list[NewsSearchItem]: 快讯列表
        """
        url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
        params = {
            "client": "web", "biz": "web_724", "fastColumn": "102",
            "sortEnd": "", "req_trace": str(int(time.time() * 1000)), "pageSize": "50",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuaixun.eastmoney.com/",
        }
        r = self.em_get_response(url, params=params, headers=headers, timeout=10)
        d = r.json()
        rows = []
        for item in d.get("data", {}).get("fastNewsList", []):
            title = str(item.get("title") or "").strip()
            content_text = str(item.get("summary") or "").strip()
            combined = f"{title}\n{content_text}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            rows.append(NewsSearchItem(
                title=title, content=content_text,
                publish_time=item.get("showTime", ""),
                url=item.get("url", ""),
                source=item.get("mediaName", "") or "东方财富快讯",
                author=item.get("author", ""),
                read_count=int(item.get("read_count", 0)),
                comment_count=int(item.get("comment_count", 0)),
            ))
        return rows

    def fetch_stock_comments(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富股吧评论。

        Param:
            code: 股票代码
            code_name: 股票名称，用于过滤相关评论
        Return:
            list[NewsSearchItem]: 评论列表
        """
        params = {
            "code": "cjpl",
            "sorttype": "1",
            "ps": "24",
            "from": "CommonBaPost",
            "deviceid": "quoteweb",
            "version": "200",
            "product": "Guba",
            "plat": "Web",
            "needzd": "true",
            "callback": "jsonp_1778666941893_8qj7w84su07",
        }
        response = self.em_get_response(
            "https://gbapi.eastmoney.com/webarticlelist/api/Article/Articlelist",
            params=params,
            headers=self.eastmoney_headers,
            timeout=10,
        )
        response.raise_for_status()
        text = response.text.strip()
        start = text.find("(") + 1
        end = text.find(")")
        payload = json.loads(text[start:end])
        results: list[NewsSearchItem] = []
        for item in payload.get("re", []):
            title = str(item.get("post_title") or "").strip()
            content = str(item.get("content") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:500],
                    source=item.get("stockbar_name", ""),
                    publish_time=str(item.get("post_publish_time", "")),
                    url=item.get("url", ""),
                    author=item.get("user_nickname", ""),
                    read_count=int(item.get("read_count", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results

    def fetch_stock_guba_posts(self, code: str = "600519", page: int = 1) -> list[NewsSearchItem]:
        """获取东方财富股吧帖子列表。

        通过解析股吧 HTML 页面获取帖子数据。

        Param:
            code: 股票代码，默认 "600519"
            page: 页码，默认 1
        Return:
            list[NewsSearchItem]: 帖子列表
        """
        url = f"http://guba.eastmoney.com/list,{code},f_{page}.html"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"http://guba.eastmoney.com/list,{code}.html",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        response = self.em_get_response(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"

        posts = self._extract_guba_article_list(response.text).get("re") or []
        results: list[NewsSearchItem] = []
        for post in posts:
            post_id = post.get("post_id", "")
            results.append(
                NewsSearchItem(
                    title=post.get("post_title", ""),
                    content=post.get("post_content", ""),
                    url=f"https://guba.eastmoney.com/news,{code},{post_id}.html",
                    publish_time=post.get("post_publish_time", ""),
                    source="eastmoney_guba",
                    author=post.get("user_nickname", "") or (post.get("post_user") or {}).get("user_nickname", ""),
                    read_count=post.get("post_click_count", 0),
                    comment_count=post.get("post_comment_count", 0),
                )
            )
        return results

    def _extract_guba_article_list(self, html: str) -> dict:
        """从股吧 HTML 中提取 article_list 数据。

        Param:
            html: 股吧页面 HTML 内容
        Return:
            dict: 包含 "re" 键的文章列表字典
        """
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            text = script.string or script.get_text()
            if not text or "var article_list" not in text:
                continue
            match = re.search(r"var\s+article_list\s*=\s*(\{.*?\})\s*;\s*var\s+other_list", text, re.S)
            if match:
                return json.loads(match.group(1))
        raise ValueError("未找到 article_list")
