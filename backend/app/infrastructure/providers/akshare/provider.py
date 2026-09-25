"""AkShare Provider 统一入口。"""

import app.infrastructure.providers.akshare.calendar as calendar
import app.infrastructure.providers.akshare.financials as financials
import app.infrastructure.providers.akshare.indices as indices
import app.infrastructure.providers.akshare.industry as industry
import app.infrastructure.providers.akshare.macro as macro
import app.infrastructure.providers.akshare.news as news
import app.infrastructure.providers.akshare.stock as stock


class AkshareDataProvider:
    name = "akshare"

    fetch_restricted_shares = staticmethod(stock.fetch_restricted_shares)
    fetch_interactive_qa = staticmethod(stock.fetch_interactive_qa)
    fetch_bond_yields = staticmethod(macro.fetch_bond_yields)

    fetch_stock_kline = staticmethod(stock.fetch_stock_kline)
    fetch_stock_kline_sina = staticmethod(stock.fetch_stock_kline_sina)
    fetch_stock_intraday_minute_sina = staticmethod(stock.fetch_stock_intraday_minute_sina)
    fetch_stock_intraday_transactions = staticmethod(stock.fetch_stock_intraday_transactions)
    fetch_stock_intraday_minute = staticmethod(stock.fetch_stock_intraday_minute)
    fetch_stock_names_sh = staticmethod(stock.fetch_stock_names_sh)
    fetch_stock_names_sz = staticmethod(stock.fetch_stock_names_sz)
    fetch_stock_names_bj = staticmethod(stock.fetch_stock_names_bj)
    fetch_stock_spot_snapshot = staticmethod(stock.fetch_stock_spot_snapshot)
    fetch_trade_dates = staticmethod(calendar.fetch_trade_dates)

    fetch_stock_financials = staticmethod(financials.fetch_stock_financials)
    fetch_stock_valuation_comparison = staticmethod(financials.fetch_stock_valuation_comparison)
    fetch_stock_valuation_baidu = staticmethod(financials.fetch_stock_valuation_baidu)

    fetch_market_indices = staticmethod(indices.fetch_market_indices)
    fetch_market_indices_sina = staticmethod(indices.fetch_market_indices_sina)
    fetch_index_kline = staticmethod(indices.fetch_index_kline)
    fetch_index_kline_sina = staticmethod(indices.fetch_index_kline_sina)
    fetch_index_kline_tencent = staticmethod(indices.fetch_index_kline_tencent)

    fetch_stock_news = staticmethod(news.fetch_stock_news)
    fetch_hot_rank_detail = staticmethod(news.fetch_hot_rank_detail)
    fetch_sw_index_realtime = staticmethod(industry.fetch_sw_index_realtime)
    fetch_sw_index_components = staticmethod(industry.fetch_sw_index_components)
    fetch_china_cpi = staticmethod(macro.fetch_china_cpi)
    fetch_china_ppi = staticmethod(macro.fetch_china_ppi)
    fetch_china_pmi = staticmethod(macro.fetch_china_pmi)
    fetch_china_economy_currency_supply = staticmethod(macro.fetch_china_economy_currency_supply)
    fetch_china_gdp = staticmethod(macro.fetch_china_gdp)
    fetch_china_lpr = staticmethod(macro.fetch_china_lpr)
    fetch_china_shibor = staticmethod(macro.fetch_china_shibor)
    fetch_china_social_financing = staticmethod(macro.fetch_china_social_financing)
    fetch_china_trade = staticmethod(macro.fetch_china_trade)

    fetch_us_gdp = staticmethod(macro.fetch_us_gdp)
    fetch_us_cpi = staticmethod(macro.fetch_us_cpi)
    fetch_us_ppi = staticmethod(macro.fetch_us_ppi)
    fetch_us_labor = staticmethod(macro.fetch_us_labor)
    fetch_us_pmi = staticmethod(macro.fetch_us_pmi)
    fetch_us_fed_rate = staticmethod(macro.fetch_us_fed_rate)
    fetch_us_retail_sales = staticmethod(macro.fetch_us_retail_sales)
    fetch_us_trade_balance = staticmethod(macro.fetch_us_trade_balance)


akshare_provider = AkshareDataProvider()
