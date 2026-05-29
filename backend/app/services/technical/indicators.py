import logging

from app.models.stock import KlineItem

logger = logging.getLogger(__name__)


def calculate_ma(closes: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            window = closes[i - period + 1 : i + 1]
            result.append(round(sum(window) / period, 2))
    return result


def calculate_ema(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    multiplier = 2 / (period + 1)
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            result.append(round(sum(values[:period]) / period, 4))
        else:
            prev = result[i - 1]
            if prev is not None:
                result.append(round((values[i] - prev) * multiplier + prev, 4))
            else:
                result.append(None)
    return result


def calculate_macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)

    dif: list[float | None] = []
    for i in range(len(closes)):
        f, s = ema_fast[i], ema_slow[i]
        if f is not None and s is not None:
            dif.append(round(f - s, 4))
        else:
            dif.append(None)

    dif_values = [v for v in dif if v is not None]
    dea = calculate_ema(dif_values, signal)

    dea_full: list[float | None] = []
    di = 0
    for v in dif:
        if v is not None:
            dea_full.append(dea[di] if di < len(dea) else None)
            di += 1
        else:
            dea_full.append(None)

    macd_hist: list[float | None] = []
    for i in range(len(closes)):
        d, e = dif[i], dea_full[i]
        if d is not None and e is not None:
            macd_hist.append(round(2 * (d - e), 4))
        else:
            macd_hist.append(None)

    return dif, dea_full, macd_hist


def calculate_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(closes)):
        if i < period:
            result.append(None)
            continue
        gains = []
        losses = []
        for j in range(i - period + 1, i + 1):
            change = closes[j] - closes[j - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-change)
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(round(100 - 100 / (1 + rs), 2))
    return result


def calculate_boll(closes: list[float], period: int = 20, std_dev: int = 2) -> tuple[list[float | None], list[float | None], list[float | None]]:
    upper: list[float | None] = []
    middle: list[float | None] = []
    lower: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1:
            upper.append(None)
            middle.append(None)
            lower.append(None)
        else:
            window = closes[i - period + 1 : i + 1]
            mid = sum(window) / period
            variance = sum((x - mid) ** 2 for x in window) / period
            std = variance**0.5
            middle.append(round(mid, 2))
            upper.append(round(mid + std_dev * std, 2))
            lower.append(round(mid - std_dev * std, 2))
    return upper, middle, lower


def calculate_kdj(
    highs: list[float], lows: list[float], closes: list[float], period: int = 9
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    k_values: list[float | None] = []
    d_values: list[float | None] = []
    j_values: list[float | None] = []

    prev_k = 50.0
    prev_d = 50.0

    for i in range(len(closes)):
        if i < period - 1:
            k_values.append(None)
            d_values.append(None)
            j_values.append(None)
        else:
            high_window = highs[i - period + 1 : i + 1]
            low_window = lows[i - period + 1 : i + 1]
            highest = max(high_window)
            lowest = min(low_window)
            if highest == lowest:
                rsv = 50.0
            else:
                rsv = (closes[i] - lowest) / (highest - lowest) * 100

            k = 2 / 3 * prev_k + 1 / 3 * rsv
            d = 2 / 3 * prev_d + 1 / 3 * k
            j = 3 * k - 2 * d

            k_values.append(round(k, 2))
            d_values.append(round(d, 2))
            j_values.append(round(j, 2))

            prev_k = k
            prev_d = d

    return k_values, d_values, j_values


def calculate_all(items: list[KlineItem]) -> dict:
    if not items:
        logger.warning("技术指标计算: K线数据为空")
        return _empty_result()

    closes = [item.close for item in items]
    highs = [item.high for item in items]
    lows = [item.low for item in items]
    volumes = [item.volume for item in items]

    ma5 = calculate_ma(closes, 5)
    ma10 = calculate_ma(closes, 10)
    ma20 = calculate_ma(closes, 20)
    ma60 = calculate_ma(closes, 60)
    dif, dea, macd_hist = calculate_macd(closes)
    rsi = calculate_rsi(closes)
    boll_upper, boll_middle, boll_lower = calculate_boll(closes)
    k, d, j = calculate_kdj(highs, lows, closes)
    volume_ma5 = calculate_ma(volumes, 5)
    volume_ma10 = calculate_ma(volumes, 10)

    latest_idx = len(items) - 1
    logger.info(f"技术指标计算完成: 数据点={len(items)}, MA5={ma5[latest_idx]}, RSI={rsi[latest_idx]}, MACD_DIF={dif[latest_idx]}")

    return {
        "ma": {
            "ma5": ma5[latest_idx],
            "ma10": ma10[latest_idx],
            "ma20": ma20[latest_idx],
            "ma60": ma60[latest_idx],
        },
        "macd": {
            "dif": dif[latest_idx],
            "dea": dea[latest_idx],
            "macd_hist": macd_hist[latest_idx],
        },
        "rsi": rsi[latest_idx],
        "boll": {
            "upper": boll_upper[latest_idx],
            "middle": boll_middle[latest_idx],
            "lower": boll_lower[latest_idx],
        },
        "kdj": {
            "k": k[latest_idx],
            "d": d[latest_idx],
            "j": j[latest_idx],
        },
        "volume_ma": {
            "ma5": volume_ma5[latest_idx],
            "ma10": volume_ma10[latest_idx],
        },
        "series": {
            "dates": [item.date for item in items],
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "dif": dif,
            "dea": dea,
            "macd_hist": macd_hist,
            "rsi": rsi,
            "boll_upper": boll_upper,
            "boll_middle": boll_middle,
            "boll_lower": boll_lower,
            "k": k,
            "d": d,
            "j": j,
        },
    }


def _empty_result() -> dict:
    return {
        "ma": {"ma5": None, "ma10": None, "ma20": None, "ma60": None},
        "macd": {"dif": None, "dea": None, "macd_hist": None},
        "rsi": None,
        "boll": {"upper": None, "middle": None, "lower": None},
        "kdj": {"k": None, "d": None, "j": None},
        "volume_ma": {"ma5": None, "ma10": None},
        "series": {
            "dates": [], "ma5": [], "ma10": [], "ma20": [], "ma60": [],
            "dif": [], "dea": [], "macd_hist": [], "rsi": [],
            "boll_upper": [], "boll_middle": [], "boll_lower": [],
            "k": [], "d": [], "j": [],
        },
    }
