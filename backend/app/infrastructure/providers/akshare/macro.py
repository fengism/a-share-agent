"""AkShare 宏观经济能力。"""

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from app.infrastructure.providers.akshare.loader import ak


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_china_gdp() -> pd.DataFrame:
    frame = ak.macro_china_gdp()
    if frame is not None and not frame.empty:
        return frame.tail(12)
    return pd.DataFrame()
