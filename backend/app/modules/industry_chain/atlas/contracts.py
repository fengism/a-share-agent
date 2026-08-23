"""产业链知识库（Atlas）契约模型。

静态策划数据按 quant 策略 definitions 的方式以 YAML 维护，
经 pydantic 校验后对外提供稳定视图。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_CODE_PATTERN = re.compile(r"^\d{6}$")


class AtlasCompany(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    code: str
    note: str = ""

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        if not _CODE_PATTERN.match(value):
            raise ValueError(f"股票代码必须是 6 位数字: {value!r}")
        return value


class AtlasSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    companies: list[AtlasCompany] = Field(min_length=1)


class AtlasLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["upstream", "midstream", "downstream"]
    name: str
    segments: list[AtlasSegment] = Field(min_length=1)


class AtlasChain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    category: str
    summary: str
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    drivers: list[str] = Field(default_factory=list)
    layers: list[AtlasLayer] = Field(min_length=1)
    """builtin=随代码内置，imported=外部导入目录提供，mined=AI 分析自动挖掘"""
    source: Literal["builtin", "imported", "mined"] = "builtin"
    """mined=由 AI 产业链分析结果自动挖掘生成（落盘在导入目录）"""
    mined: bool = False

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str) -> str:
        if not _SLUG_PATTERN.match(value):
            raise ValueError(f"slug 只允许小写字母/数字/连字符: {value!r}")
        return value

    @field_validator("layers")
    @classmethod
    def _validate_layers(cls, value: list[AtlasLayer]) -> list[AtlasLayer]:
        keys = [layer.key for layer in value]
        if len(keys) != len(set(keys)):
            raise ValueError("每条链的 upstream/midstream/downstream 层不能重复")
        return value

    @property
    def segment_count(self) -> int:
        return sum(len(layer.segments) for layer in self.layers)

    @property
    def company_count(self) -> int:
        return sum(
            len(segment.companies)
            for layer in self.layers
            for segment in layer.segments
        )


class AtlasChainSummary(BaseModel):
    slug: str
    name: str
    category: str
    summary: str
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    segment_count: int
    company_count: int
    source: Literal["builtin", "imported", "mined"] = "builtin"


class AtlasCatalog(BaseModel):
    categories: list[str]
    chains: list[AtlasChainSummary]
    total_chains: int
    total_companies: int
