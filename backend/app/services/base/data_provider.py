from dataclasses import dataclass


@dataclass(frozen=True)
class BaseDataProvider:
    name: str
    source_label: str

    def log_prefix(self, capability: str) -> str:
        return f"{self.source_label}{capability}"
