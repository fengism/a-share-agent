from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.infrastructure.llm.prompting.parsing import parse_model_response
from app.infrastructure.llm.prompting.policies import (
    UNTRUSTED_CONTEXT_POLICY,
    render_schema_contract,
    wrap_untrusted_context,
)

OutputT = TypeVar("OutputT", bound=BaseModel)
PromptContext = Mapping[str, Any]


@dataclass(frozen=True)
class PromptSpec(Generic[OutputT]):
    """版本化 Prompt 定义，集中声明渲染、输出契约和运行参数。"""

    id: str
    version: str
    system_prompt: str
    user_builder: Callable[[PromptContext], str]
    output_model: type[OutputT]
    temperature: float = 0.1
    repair_attempts: int = 1
    untrusted_context: bool = True
    parser: Callable[[str], OutputT] | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.version.strip():
            raise ValueError("Prompt id/version 不能为空")
        if self.repair_attempts < 0:
            raise ValueError("repair_attempts 不能小于 0")

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def render(self, context: PromptContext) -> list[dict[str, str]]:
        system_parts = [self.system_prompt.strip()]
        if self.untrusted_context:
            system_parts.append(UNTRUSTED_CONTEXT_POLICY)
        system_parts.append(render_schema_contract(self.output_model))
        user_content = self.user_builder(context).strip()
        if self.untrusted_context:
            user_content = wrap_untrusted_context(user_content)
        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            {"role": "user", "content": user_content},
        ]

    def parse(self, raw_text: str) -> OutputT:
        if self.parser is not None:
            return self.parser(raw_text)
        return parse_model_response(raw_text, self.output_model)

    def cache_key(self, *parts: object) -> str:
        suffix = ":".join(str(part) for part in parts)
        prefix = f"prompt:{self.id}:{self.version}"
        return f"{prefix}:{suffix}" if suffix else prefix
