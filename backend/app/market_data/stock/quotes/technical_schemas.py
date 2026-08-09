from pydantic import BaseModel, Field


class TechnicalMovingAverages(BaseModel):
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None


class TechnicalMacd(BaseModel):
    dif: float | None = None
    dea: float | None = None
    macd_hist: float | None = None


class TechnicalBoll(BaseModel):
    upper: float | None = None
    middle: float | None = None
    lower: float | None = None


class TechnicalKdj(BaseModel):
    k: float | None = None
    d: float | None = None
    j: float | None = None


class TechnicalVolumeAverages(BaseModel):
    ma5: float | None = None
    ma10: float | None = None


class TechnicalSeries(BaseModel):
    dates: list[str] = Field(default_factory=list)
    ma5: list[float | None] = Field(default_factory=list)
    ma10: list[float | None] = Field(default_factory=list)
    ma20: list[float | None] = Field(default_factory=list)
    ma60: list[float | None] = Field(default_factory=list)
    dif: list[float | None] = Field(default_factory=list)
    dea: list[float | None] = Field(default_factory=list)
    macd_hist: list[float | None] = Field(default_factory=list)
    rsi: list[float | None] = Field(default_factory=list)
    boll_upper: list[float | None] = Field(default_factory=list)
    boll_middle: list[float | None] = Field(default_factory=list)
    boll_lower: list[float | None] = Field(default_factory=list)
    k: list[float | None] = Field(default_factory=list)
    d: list[float | None] = Field(default_factory=list)
    j: list[float | None] = Field(default_factory=list)


class TechnicalIndicators(BaseModel):
    """Purpose: 技术指标的最新快照及完整时间序列。"""

    ma: TechnicalMovingAverages
    macd: TechnicalMacd
    rsi: float | None = None
    boll: TechnicalBoll
    kdj: TechnicalKdj
    volume_ma: TechnicalVolumeAverages
    series: TechnicalSeries
