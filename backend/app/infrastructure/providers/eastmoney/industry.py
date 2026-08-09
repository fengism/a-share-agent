import logging

import pandas as pd

from app.constants.market import EASTMONEY_UT_TRADE

logger = logging.getLogger(__name__)



class IndustryMixin:
    """东方财富 industry 数据接口。"""

    def fetch_industry_boards(self) -> pd.DataFrame:
        """获取东财行业板块列表。

        Return:
            pd.DataFrame: 包含列: 板块代码, 板块名称
        """
        params = {
            "po": "1",
            "np": "1",
            "ut": EASTMONEY_UT_TRADE,
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:90 t:2 f:!50",
            "fields": "f12,f14",
        }
        diff = self._fetch_clist_diff(params, page_size=200)
        if not diff:
            return pd.DataFrame(columns=["板块代码", "板块名称"])

        df = pd.DataFrame(diff).rename(columns={"f12": "板块代码", "f14": "板块名称"})
        keep_cols = [column for column in ["板块代码", "板块名称"] if column in df.columns]
        return df[keep_cols]

    def fetch_industry_components(self, board_code: str) -> pd.DataFrame:
        """获取指定行业板块的成分股列表。

        Param:
            board_code: 行业板块代码
        Return:
            pd.DataFrame: 包含列: 代码, 名称
        """
        params = {
            "po": "1",
            "np": "1",
            "ut": EASTMONEY_UT_TRADE,
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": f"b:{board_code} f:!50",
            "fields": "f12,f14",
        }
        diff = self._fetch_clist_diff(params, page_size=200)
        if not diff:
            return pd.DataFrame(columns=["代码", "名称"])

        df = pd.DataFrame(diff).rename(columns={"f12": "代码", "f14": "名称"})
        keep_cols = [column for column in ["代码", "名称"] if column in df.columns]
        return df[keep_cols]

    def build_industry_mapping(self) -> tuple[dict[str, str], list[str]]:
        """构建股票代码到行业板块的映射关系。

        遍历所有行业板块，获取每个板块的成分股，建立映射。

        Return:
            tuple[dict[str, str], list[str]]:
                - dict: 股票代码 -> 行业板块名称 的映射
                - list: 所有行业板块名称列表
        """
        boards_df = self.fetch_industry_boards()
        mapping: dict[str, str] = {}
        industries: list[str] = []
        if "板块名称" in boards_df.columns:
            industries = boards_df["板块名称"].dropna().astype(str).tolist()

        if boards_df.empty or "板块代码" not in boards_df.columns or "板块名称" not in boards_df.columns:
            return mapping, industries

        for _, row in boards_df.iterrows():
            board_code = str(row["板块代码"])
            board_name = str(row["板块名称"])
            try:
                cons_df = self.fetch_industry_components(board_code)
                if "代码" not in cons_df.columns:
                    continue
                for code in cons_df["代码"]:
                    stock_code = str(code).strip().zfill(6)
                    if stock_code and stock_code.isdigit():
                        mapping[stock_code] = board_name
            except Exception as exc:
                logger.warning(f"东方财富直连获取行业成分失败: {board_name}({board_code}), error={exc}")
                continue
        return mapping, industries

    def fetch_industry_rankings(self, top_n: int = 20) -> dict:
        """获取全行业涨跌幅排名。

        获取东财行业板块（约 100 个行业）的涨跌幅排名。

        Param:
            top_n: 返回前 N 名和后 N 名，默认 20
        Return:
            dict: 包含以下字段:
                - top (list): 涨幅前 N 名列表，每个元素包含 rank, name, change_pct, code, up_count, down_count, leader, leader_change
                - bottom (list): 跌幅前 N 名列表（同上结构）
                - total (int): 行业总数
        """
        params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        items = self._fetch_clist_diff(params=params, headers=self.eastmoney_headers)
        if not items:
            return {"top": [], "bottom": [], "total": 0}

        rows = []
        for i, item in enumerate(items):
            rows.append({
                "rank": i + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "code": item.get("f12", ""),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": item.get("f136", 0),
            })

        return {
            "top": rows[:top_n],
            "bottom": rows[-top_n:],
            "total": len(rows),
        }

    def fetch_concept_rankings(self, top_n: int = 20) -> dict:
        """获取全概念涨跌幅排名。

        获取东财概念板块（约 100 个概念）的涨跌幅排名。

        Param:
            top_n: 返回前 N 名和后 N 名，默认 20
        Return:
            dict: 包含以下字段:
                - top (list): 涨幅前 N 名列表，每个元素包含 rank, name, change_pct, code, up_count, down_count, leader, leader_change
                - bottom (list): 跌幅前 N 名列表（同上结构）
                - total (int): 行业总数
        """
        url = "https://push2.eastmoney.com/webguest/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:90+t:3+f:!50",
            "dect": "1",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        items = self._fetch_clist_diff(params=params, headers=self.eastmoney_headers, url=url)
        if not items:
            return {"top": [], "bottom": [], "total": 0}

        rows = []
        for i, item in enumerate(items):
            rows.append({
                "rank": i + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "code": item.get("f12", ""),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": item.get("f136", 0),
            })

        return {
            "top": rows[:top_n],
            "bottom": rows[-top_n:],
            "total": len(rows),
        }
