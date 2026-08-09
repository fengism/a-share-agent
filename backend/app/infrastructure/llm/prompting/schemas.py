from pydantic import BaseModel


class PromptTrace(BaseModel):
    """Purpose: 记录生成结果所使用的 Prompt 与模型配置，便于回溯。"""

    prompt_id: str
    prompt_version: str
    model: str = ""
    temperature: float = 0.0
    input_digest: str
    generated_at: str
    attempts: int = 1
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
