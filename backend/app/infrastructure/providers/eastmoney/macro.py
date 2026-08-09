import logging

logger = logging.getLogger(__name__)



class MacroMixin:
    """东方财富 macro 数据接口。"""

    def fetch_china_cpi(self):
        """
        中国CPI数据。
        https://datacenter-web.eastmoney.com/api/data/v1/get?columns=REPORT_DATE%2CTIME%2CNATIONAL_SAME%2CNATIONAL_BASE%2CNATIONAL_SEQUENTIAL%2CNATIONAL_ACCUMULATE%2CCITY_SAME%2CCITY_BASE%2CCITY_SEQUENTIAL%2CCITY_ACCUMULATE%2CRURAL_SAME%2CRURAL_BASE%2CRURAL_SEQUENTIAL%2CRURAL_ACCUMULATE&pageNumber=1&pageSize=20&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_CPI&_=1780832254645
        Return:
            list[dict]: 中国CPI数据列表，每个字典包含:
                - date (str): 日期
                - CITY_SAME (float): 城市CPI
                - CITY_BASE (float): 城市CPI（基数）
                - CITY_SEQUENTIAL (float): 城市CPI(环比)
                - CITY_ACCUMULATE (float): 城市CPI(累计)
                - RURAL_SAME (float): 农村CPI
                - RURAL_BASE (float): 农村CPI（基数）
                - RURAL_SEQUENTIAL (float): 农村CPI(环比)
                - RURAL_ACCUMULATE (float): 农村CPI(累计)
                - NATIONAL_SAME (float): 国家CPI
                - NATIONAL_BASE (float): 国家CPI（基数）、            
                - NATIONAL_SEQUENTIAL (float): 国家CPI(环比)
                - NATIONAL_ACCUMULATE (float): 国家CPI(累计)
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_CPI",
            filter_str="(REPORT_DATE >= '2023-01-01')",
            columns="REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_BASE,NATIONAL_SEQUENTIAL,NATIONAL_ACCUMULATE,CITY_SAME,CITY_BASE,CITY_SEQUENTIAL,CITY_ACCUMULATE,RURAL_SAME,RURAL_BASE,RURAL_SEQUENTIAL,RURAL_ACCUMULATE",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        
        return data

    def fetch_china_ppi(self):
        """
        中国工业品出厂价格指数（PPI）
        Return:
            list[dict]: 中国工业品出厂价格指数（PPI）数据列表，每个字典包含:
                - TIME (str): 日期
                - BASE (float): 当月PPI
                - BASE_SAME (float): 当月PPI同比增长
                - BASE_ACCUMULATE (float): PPI累计
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_PPI",
            filter_str="(REPORT_DATE >= '2023-01-01')",
            columns="REPORT_DATE,TIME,BASE,BASE_SAME,BASE_ACCUMULATE",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_pmi(self):
        """
        中国采购经理人指数（PMI）
        Return:
            list[dict]: 中国采购经理人指数（PMI）数据列表，每个字典包含:
                - REPORT_DATE (str): 日期
                - TIME (str): 日期
                - MAKE_INDEX (float): 制造业指数
                - MAKE_SAME (float): 制造业指数(环比)
                - NMAKE_INDEX (float): 非制造业指数
                - NMAKE_SAME (float): 非制造业指数(环比)
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_PMI",
            filter_str="(REPORT_DATE >= '2025-01-01')",
            columns="REPORT_DATE,TIME,MAKE_INDEX,MAKE_SAME,NMAKE_INDEX,NMAKE_SAME",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_economy_currency_supply(self):
        """
        中国货币供应指数（货币供应）
        Return:
            list[dict]: 中国货币供应指数（货币供应指数）数据列表，每个字典包含:
                - REPORT_DATE (str): 日期
                - TIME (str): 日期
                - BASIC_CURRENCY (float): M2数量(亿元)
                - BASIC_CURRENCY_SAME (float): M2数量同比增长
                - BASIC_CURRENCY_SEQUENTIAL (float): M2数量环比
                - CURRENCY (float): 货币供应指数M1(亿元)
                - CURRENCY_SAME (float): 货币供应指数M1同比增长
                - CURRENCY_SEQUENTIAL (float): 货币供应指数M1(环比)
                - FREE_CASH (float): 流通中现金指数M0(亿元)
                - FREE_CASH_SAME (float): 流通中现金指数M0同比增长
                - FREE_CASH_SEQUENTIAL (float): 流通中现金指数M0环比    
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_CURRENCY_SUPPLY",
            filter_str="(REPORT_DATE >= '2025-01-01')",
            columns="REPORT_DATE,TIME,BASIC_CURRENCY,BASIC_CURRENCY_SAME,BASIC_CURRENCY_SEQUENTIAL,CURRENCY,CURRENCY_SAME,CURRENCY_SEQUENTIAL,FREE_CASH,FREE_CASH_SAME,FREE_CASH_SEQUENTIAL",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_lpr(self):
        """
        中国贷款市场报价利率（LPR）
        Return:
            list[dict]: LPR数据列表，每个字典包含:
                - TRADE_DATE (str): 日期
                - LPR1Y (float): 1年期LPR
                - LPR5Y (float): 5年期以上LPR
                - RATE_1 (float): 短期贷款利率
                - RATE_2 (float): 中长期贷款利率
        """
        data = self.fetch_datacenter_report(
            "RPTA_WEB_RATE",
            columns="ALL",
            page_size=20,
            sort_columns="TRADE_DATE", sort_types="-1",
        )
        return data

    def fetch_china_gdp(self):
        """
        中国GDP数据
        Return:
            list[dict]: GDP数据列表，每个字典包含:
                - TIME (str): 日期
                - REPORT_DATE (str): 日期
                - DOMESTICL_PRODUCT_BASE (float): 国内生产总值
                - FIRST_PRODUCT_BASE (float): 第一产业生产总值
                - FIRST_SAME (float): 第一产业生产总值同比增长
                - SECOND_PRODUCT_BASE (float): 第二产业生产总值
                - SECOND_SAME (float): 第二产业生产总值同比增长
                - THIRD_PRODUCT_BASE (float): 第三产业生产总值
                - THIRD_SAME (float): 第三产业生产总值同比增长
                - SUM_SAME (float): GDP同比增长
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_GDP",
            columns="REPORT_DATE,TIME,DOMESTICL_PRODUCT_BASE,FIRST_PRODUCT_BASE,SECOND_PRODUCT_BASE,THIRD_PRODUCT_BASE,SUM_SAME,FIRST_SAME,SECOND_SAME,THIRD_SAME",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_shibor(self):
        """
        上海银行间同业拆放利率（SHIBOR）
        Return:
            list[dict]: SHIBOR数据列表，每个字典包含:
                - REPORT_DATE (str): 日期
                - REPORT_PERIOD (str): 报告周期
                - IR_RATE (float): 利率
                - CHANGE_RATE (float): 利率(环比)
                - INDICATOR_ID (str): 指标ID
                - LATEST_RECORD (int): 最新记录标志
                - MARKET (str): 市场
                - MARKET_CODE (str): 市场代码
                - CURRENCY (str): 货币
                - CURRENCY_CODE (str): 货币代码
        """
        data = self.fetch_datacenter_report(
            "RPT_IMP_INTRESTRATEN",
            filter_str="(LATEST_RECORD=1)(MARKET_CODE='001')",
            columns="REPORT_DATE,REPORT_PERIOD,IR_RATE,CHANGE_RATE,INDICATOR_ID,LATEST_RECORD,MARKET,MARKET_CODE,CURRENCY,CURRENCY_CODE",
            page_size=20,
            sort_columns="INDICATOR_ID", sort_types="-1",
        )
        return data

    def fetch_china_trade(self):
        """
        中国进出口贸易数据
        Return:
            list[dict]: 进出口数据列表，每个字典包含:
                - TIME (str): 日期
                - REPORT_DATE (str): 日期
                - EXIT_ACCUMULATE (float): 出口累计
                - EXIT_ACCUMULATE_SAME (float): 出口累计同比
                - EXIT_BASE (float): 出口量
                - EXIT_BASE_SAME (float): 出口同比
                - EXIT_BASE_SEQUENTIAL (float): 出口环比
                - IMPORT_ACCUMULATE (float): 进口累计
                - IMPORT_ACCUMULATE_SAME (float): 进口累计同比
                - IMPORT_BASE (float): 进口量
                - IMPORT_BASE_SAME (float): 进口同比
                - IMPORT_BASE_SEQUENTIAL (float): 进口环比
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_CUSTOMS",
            columns="REPORT_DATE,TIME,EXIT_BASE,IMPORT_BASE,EXIT_BASE_SAME,IMPORT_BASE_SAME,EXIT_BASE_SEQUENTIAL,IMPORT_BASE_SEQUENTIAL,EXIT_ACCUMULATE,IMPORT_ACCUMULATE,EXIT_ACCUMULATE_SAME,IMPORT_ACCUMULATE_SAME",
            page_size=24,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_social_financing(self):
        """
        中国社会融资规模
        Return:
            list[dict]: 社融数据列表，每个字典包含:
                - TIME (str): 日期
                - REPORT_DATE (str): 日期
                - RMB_LOAN (float): 新增贷款
                - RMB_LOAN_SAME (float): 新增贷款同比
                - RMB_LOAN_SEQUENTIAL (float): 新增贷款环比
                - RMB_LOAN_ACCUMULATE (float): 新增贷款累计
                - LOAN_ACCUMULATE_SAME (float): 新增贷款累计同比
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_RMB_LOAN",
            columns="REPORT_DATE,TIME,RMB_LOAN,RMB_LOAN_SAME,RMB_LOAN_SEQUENTIAL,RMB_LOAN_ACCUMULATE,LOAN_ACCUMULATE_SAME",
            page_size=24,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data
