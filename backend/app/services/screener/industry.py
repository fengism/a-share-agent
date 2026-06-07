import json
import logging
from pathlib import Path

from app.services.providers.akshare import akshare_provider as _akshare_provider
from app.services.providers.eastmoney import eastmoney_provider as _eastmoney_provider
from app.utils.cache import cache, dated_cache_key
from app.utils.rate_limiter import call_blocking

logger = logging.getLogger(__name__)

_INDUSTRY_MAPPING_FILE = Path(__file__).resolve().parents[3] / "data" / "industry_second_mapping.json"
_INDUSTRY_MAPPING_CACHE_KEY = "industry_second_mapping_file"
_INDUSTRY_LIST_CACHE_KEY = "industry_second_list_file"
_INDUSTRY_MAPPING_TTL = 24 * 60 * 60
_MIN_VALID_MAPPING_SIZE = 4000


def _is_valid_mapping(mapping: dict[str, str]) -> bool:
    """判断行业映射条目数量是否达到有效阈值。

    Param:
        mapping: 股票代码到行业名称的映射
    Return:
        映射条目数量超过最小阈值时返回 True
    """
    return len(mapping) > _MIN_VALID_MAPPING_SIZE


def _build_industry_list(mapping: dict[str, str]) -> list[str]:
    """根据映射构造去重排序后的行业名称列表。

    Param:
        mapping: 股票代码到行业名称的映射
    Return:
        排序后的唯一行业名称列表
    """
    return sorted(set(mapping.values()))


def _load_mapping_file() -> dict[str, str]:
    """从本地 JSON 文件加载行业映射。

    Param:
        无
    Return:
        股票代码到行业名称的字典
    """
    with _INDUSTRY_MAPPING_FILE.open("r", encoding="utf-8") as file:
        mapping = json.load(file)
    if not isinstance(mapping, dict):
        raise ValueError("行业映射文件格式异常")
    return {str(code): str(industry) for code, industry in mapping.items()}


def _get_cached_pair(mapping_key: str, list_key: str) -> tuple[dict[str, str], list[str]] | None:
    """从缓存中读取映射和行业列表对。

    Param:
        mapping_key: 映射缓存键
        list_key: 行业列表缓存键
    Return:
        命中时返回 (映射, 行业列表) 元组，否则返回 None
    """
    cached_mapping = cache.get(mapping_key)
    cached_industry_list = cache.get(list_key)
    if cached_mapping is not None and cached_industry_list is not None:
        return cached_mapping, cached_industry_list
    return None


def _cache_pair(mapping_key: str, list_key: str, mapping: dict[str, str], industry_list: list[str]) -> None:
    """将映射和行业列表写入缓存。

    Param:
        mapping_key: 映射缓存键
        list_key: 行业列表缓存键
        mapping: 股票代码到行业名称的映射
        industry_list: 行业名称列表
    Return:
        无
    """
    cache.set(mapping_key, mapping, ttl=_INDUSTRY_MAPPING_TTL)
    cache.set(list_key, industry_list, ttl=_INDUSTRY_MAPPING_TTL)


def _cache_industry_mapping(mapping: dict[str, str], industry_list: list[str]) -> None:
    """缓存文件加载的行业映射数据。

    Param:
        mapping: 股票代码到行业名称的映射
        industry_list: 行业名称列表
    Return:
        无
    """
    _cache_pair(_INDUSTRY_MAPPING_CACHE_KEY, _INDUSTRY_LIST_CACHE_KEY, mapping, industry_list)


def _built_cache_keys() -> tuple[str, str]:
    """生成构建态缓存键对。

    Param:
        无
    Return:
        (映射缓存键, 列表缓存键) 元组
    """
    return dated_cache_key("industry_second_mapping"), dated_cache_key("industry_second_list")


def _cache_built_mapping(mapping: dict[str, str], industry_list: list[str]) -> None:
    """缓存动态构建的行业映射数据。

    Param:
        mapping: 股票代码到行业名称的映射
        industry_list: 行业名称列表
    Return:
        无
    """
    mapping_key, list_key = _built_cache_keys()
    _cache_pair(mapping_key, list_key, mapping, industry_list)



def _pick_first_column(columns: list[str], candidates: list[str]) -> str | None:
    """从候选列名中选出第一个存在的列。

    Param:
        columns: DataFrame 实际列名列表
        candidates: 优先匹配的候选列名列表
    Return:
        命中的列名，找不到时返回 None
    """
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _normalize_sw_industry_name(value: object) -> str | None:
    """规范化申万行业名称，去除空白和"(申万)"后缀。

    Param:
        value: 原始行业名称值
    Return:
        规范化后的行业名称，无效时返回 None
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if text.endswith("(申万)"):
        text = text[:-4].strip()
    return text or None


def _build_industry_mapping_sw_second_index_akshare() -> tuple[dict[str, str], list[str]]:
    """
    申万二级行业映射实时数据
    """
    index_df = _akshare_provider.fetch_sw_index_realtime()
    if index_df is None or index_df.empty:
        return {}, []

    code_col = _pick_first_column(index_df.columns.tolist(), ["指数代码", "行业代码", "code"])
    name_col = _pick_first_column(index_df.columns.tolist(), ["指数名称", "行业名称", "name"])
    if code_col is None or name_col is None:
        logger.warning(f"申万二级行业指数列表字段异常: columns={index_df.columns.tolist()}")
        return {}, []

    mapping: dict[str, str] = {}
    industries: list[str] = []
    for _, row in index_df.iterrows():
        industry_code = str(row[code_col]).strip()
        industry_name = _normalize_sw_industry_name(row[name_col])
        if not industry_code or not industry_name:
            continue

        industries.append(industry_name)
        try:
            cons_df = _akshare_provider.fetch_sw_index_components(symbol=industry_code)
            if cons_df is None or cons_df.empty:
                continue
            stock_col = _pick_first_column(cons_df.columns.tolist(), ["证券代码", "股票代码", "代码"])
            if stock_col is None:
                logger.warning(
                    f"申万二级行业成分字段异常: industry={industry_name}, columns={cons_df.columns.tolist()}"
                )
                continue
            for code in cons_df[stock_col]:
                stock_code = str(code).strip().zfill(6)
                if stock_code and stock_code.isdigit():
                    mapping[stock_code] = industry_name
        except Exception as exc:
            logger.warning(f"获取申万二级行业成分失败: {industry_name}({industry_code}), error={exc}")

    return mapping, sorted(set(industries))


def _build_industry_mapping_sw_second() -> tuple[dict[str, str], list[str]]:
    """
    申万二级行业映射
    https://www.akshare.cn/industry.html
    :return: 行业映射字典，键为股票代码，值为行业名称
    """
    mapping_key, list_key = _built_cache_keys()
    cached = _get_cached_pair(mapping_key, list_key)
    if cached is not None:
        return cached

    try:
        mapping, industry_list = _build_industry_mapping_sw_second_index_akshare()
        if _is_valid_mapping(mapping):
            _cache_built_mapping(mapping, industry_list)
            return mapping, industry_list
        logger.info(f"申万二级行业列表数据量不足: count={len(mapping)}")
    except Exception as e:
        logger.info(f"申万二级行业列表不可用: {e}")

    try:
        mapping, industry_list = _eastmoney_provider.build_industry_mapping()
        if _is_valid_mapping(mapping):
            _cache_built_mapping(mapping, industry_list)
            return mapping, industry_list
        logger.info(f"东方财富直连行业列表数据量不足: count={len(mapping)}")
    except Exception as e:
        logger.info(f"东方财富直连获取行业列表失败: {e}")

    return {}, []


def fetch_industry_mapping_sw_second() -> tuple[dict[str, str], list[str]]:
    """同步获取申万二级行业映射，优先用缓存与本地文件。

    Param:
        无
    Return:
        (股票代码→行业名称映射, 行业名称列表) 元组
    """
    cached = _get_cached_pair(_INDUSTRY_MAPPING_CACHE_KEY, _INDUSTRY_LIST_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        mapping = _load_mapping_file()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"行业映射文件不可用，尝试重新生成: path={_INDUSTRY_MAPPING_FILE}, error={exc}")
        mapping, industry_list = update_industry_mapping_sw_second_file()
    else:
        industry_list = _build_industry_list(mapping)

    _cache_industry_mapping(mapping, industry_list)
    return mapping, industry_list

def update_industry_mapping_sw_second_file() -> tuple[dict[str, str], list[str]]:
    """重新构建申万二级行业映射并写回本地文件。

    Param:
        无
    Return:
        (股票代码→行业名称映射, 行业名称列表) 元组
    """
    mapping, industry_list = _build_industry_mapping_sw_second()
    if not _is_valid_mapping(mapping):
        return mapping, industry_list

    _INDUSTRY_MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _INDUSTRY_MAPPING_FILE.open("w", encoding="utf-8") as file:
        json.dump(mapping, file, ensure_ascii=False, indent=2, sort_keys=True)
    _cache_industry_mapping(mapping, industry_list)
    return mapping, industry_list

async def build_industry_mapping() -> tuple[dict[str, str], list[str]]:
    """异步获取申万二级行业映射及行业列表。

    Param:
        无
    Return:
        (股票代码→行业名称映射, 行业名称列表) 元组
    """
    mapping, industry_list = await call_blocking(fetch_industry_mapping_sw_second)
    return mapping, industry_list


async def get_industry_mapping() -> dict[str, str]:
    """异步获取申万二级行业映射。

    Param:
        无
    Return:
        股票代码到行业名称的字典
    """
    mapping, _ = await call_blocking(fetch_industry_mapping_sw_second)
    return mapping


async def get_industry_list() -> list[str]:
    """异步获取申万二级行业名称列表。

    Param:
        无
    Return:
        行业名称字符串列表
    """
    _, industry_list = await call_blocking(fetch_industry_mapping_sw_second)
    return industry_list


if __name__ == "__main__":
    update_industry_mapping_sw_second_file()