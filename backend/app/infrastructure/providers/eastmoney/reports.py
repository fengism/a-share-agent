import logging
import time

import pandas as pd

logger = logging.getLogger(__name__)


class ReportsMixin:
    """东方财富 reports 数据接口。"""

    def fetch_stock_forecast_reports(self, code: str, max_pages: int = 5) -> pd.DataFrame:
        """获取指定股票的机构研报预测数据。

        拉取近 100 天内的机构研报，汇总 EPS 和 PE 预测统计。

        Param:
            code: 股票代码
            max_pages: 最大拉取页数，默认 5
        Return:
            pd.DataFrame: 包含列: 指标, 年度, 预测机构数, 最小值, 平均值, 最大值, 行业平均数, 单位
        """
        all_records = []
        end_time = time.strftime("%Y-%m-%d")
        begin_time = time.strftime("%Y-%m-%d", time.localtime(time.time() - 100 * 24 * 3600))
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*", "pageSize": "100", "industry": "*",
                "rating": "*", "ratingChange": "*",
                "beginTime": begin_time, "endTime": end_time,
                "pageNo": str(page), "fields": "", "qType": "0",
                "orgCode": "", "code": code, "rcode": "",
                "p": str(page), "pageNum": str(page), "pageNumber": str(page),
            }
            r = self.em_get_response(self.REPORT_API, params=params,
                                     headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
            d = r.json()
            rows = d.get("data") or []
            if not rows:
                break
            
            all_records.extend([{"code": code,  
                                 "indvInduName": row.get("indvInduName", ""),
                                 "publishDate": row.get("publishDate", ""), 
                                 "orgName": row.get("orgName", ""),
                                 "recomend_rating": row.get("emRatingName", ""),
                                 "predictThisYearEps": row.get("predictThisYearEps", ""),
                                 "predictThisYearPe": row.get("predictThisYearPe", ""),
                                 "predictNextYearEps": row.get("predictNextYearEps", ""),
                                 "predictNextYearPe": row.get("predictNextYearPe", "")
                                 } 
                                for row in rows])
            
            if page >= (d.get("TotalPage", 1) or 1):
                break
            
            time.sleep(0.3)
        df = pd.DataFrame(all_records)
        predict_stat_dict = []
        predict_stat_df = pd.DataFrame(columns=["指标", "年度", "预测机构数", "最小值", "平均值", "最大值", "行业平均数", "单位"])
        if not df.empty:
            num_orgs = df["orgName"].nunique()
            this_year = str(time.localtime().tm_year)
            next_year = str(time.localtime().tm_year + 1)
            year_labels = {
                "predictThisYearEps": ("EPS", this_year),
                "predictThisYearPe": ("PE", this_year),
                "predictNextYearEps": ("EPS", next_year),
                "predictNextYearPe": ("PE", next_year),
            }
            for col in year_labels:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            predict_stat_dict = []
            for col, (metric, year) in year_labels.items():
                label = f"{metric}"
                valid = df[col].dropna()
                if valid.empty:
                    logger.debug("东方财富研报预测无有效数据: code=%s, metric=%s", code, label)
                else:
                    min_value = f"{valid.min():.2f}"
                    max_value = f"{valid.max():.2f}"
                    mean = f"{valid.mean():.2f}"
                    predict_stat_dict.append({"指标": label, "年度": year, "预测机构数": num_orgs,"最小值": min_value, "平均值": mean, "最大值": max_value, "行业平均数": None, "单位": "单位：元"})
            predict_stat_df = pd.DataFrame(predict_stat_dict)
        return predict_stat_df
