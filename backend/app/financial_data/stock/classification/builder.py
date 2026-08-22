import logging
from collections.abc import Callable

ColumnPicker = Callable[[list[str], list[str]], str | None]
NameNormalizer = Callable[[object], str | None]
ComponentLoader = Callable[[str], object]


def pick_first_column(columns: list[str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def normalize_sw_industry_name(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if text.endswith("(申万)"):
        text = text[:-4].strip()
    return text or None


def build_akshare_mapping(
    index_dataframe,
    component_loader: ComponentLoader,
    logger: logging.Logger,
    column_picker: ColumnPicker = pick_first_column,
    name_normalizer: NameNormalizer = normalize_sw_industry_name,
) -> tuple[dict[str, str], list[str]]:
    if index_dataframe is None or index_dataframe.empty:
        return {}, []

    columns = index_dataframe.columns.tolist()
    code_column = column_picker(columns, ["指数代码", "行业代码", "code"])
    name_column = column_picker(columns, ["指数名称", "行业名称", "name"])
    if code_column is None or name_column is None:
        logger.warning("申万二级行业指数列表字段异常: columns=%s", columns)
        return {}, []

    mapping: dict[str, str] = {}
    industries: list[str] = []
    for _, row in index_dataframe.iterrows():
        industry_code = str(row[code_column]).strip()
        industry_name = name_normalizer(row[name_column])
        if not industry_code or not industry_name:
            continue

        industries.append(industry_name)
        try:
            component_dataframe = component_loader(industry_code)
            if component_dataframe is None or component_dataframe.empty:
                continue
            component_columns = component_dataframe.columns.tolist()
            stock_column = column_picker(component_columns, ["证券代码", "股票代码", "代码"])
            if stock_column is None:
                logger.warning(
                    "申万二级行业成分字段异常: industry=%s, columns=%s",
                    industry_name,
                    component_columns,
                )
                continue
            for code in component_dataframe[stock_column]:
                stock_code = str(code).strip().zfill(6)
                if stock_code and stock_code.isdigit():
                    mapping[stock_code] = industry_name
        except Exception as exc:
            logger.warning(
                "获取申万二级行业成分失败: %s(%s), error=%s",
                industry_name,
                industry_code,
                exc,
            )

    return mapping, sorted(set(industries))
