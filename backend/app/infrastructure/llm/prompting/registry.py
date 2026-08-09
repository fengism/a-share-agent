from app.infrastructure.llm.prompting.spec import PromptSpec


class PromptRegistry:
    """按稳定 ID 和版本保存本进程可用的 PromptSpec。"""

    def __init__(self) -> None:
        self._specs: dict[tuple[str, str], PromptSpec] = {}
        self._latest: dict[str, PromptSpec] = {}

    def register(self, spec: PromptSpec) -> PromptSpec:
        key = (spec.id, spec.version)
        existing = self._specs.get(key)
        if existing is not None and existing is not spec:
            raise ValueError(f"Prompt 已注册: {spec.id}@{spec.version}")
        self._specs[key] = spec
        self._latest[spec.id] = spec
        return spec

    def get(self, prompt_id: str, version: str | None = None) -> PromptSpec:
        if version is None:
            spec = self._latest.get(prompt_id)
        else:
            spec = self._specs.get((prompt_id, version))
        if spec is None:
            suffix = f"@{version}" if version else ""
            raise KeyError(f"Prompt 未注册: {prompt_id}{suffix}")
        return spec

    def clear(self) -> None:
        self._specs.clear()
        self._latest.clear()


prompt_registry = PromptRegistry()
