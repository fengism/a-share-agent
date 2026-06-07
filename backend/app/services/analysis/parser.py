import json
import logging
import re

from pydantic import ValidationError

from app.models.analysis import AnalysisResult

logger = logging.getLogger(__name__)


def extract_json(text: str) -> str:
    """Extract a JSON string from raw LLM output, stripping markdown or extra prose.

    Param:
        text: raw LLM response text potentially containing JSON in a code block
    Return:
        cleaned JSON string ready for json.loads
    """
    # 尝试从 markdown 代码块中提取
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 尝试找到第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text.strip()


def parse_analysis_response(raw_text: str) -> AnalysisResult:
    """Parse LLM output text into a validated AnalysisResult object.

    Param:
        raw_text: raw LLM response text containing analysis JSON
    Return:
        validated AnalysisResult instance
    """
    json_str = extract_json(raw_text)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"LLM输出JSON解析失败: {e}")
        logger.debug(f"Raw output: {raw_text[:500]}")
        raise ValueError(f"LLM输出不是有效的JSON: {e}")

    # 处理 estimated_price_range 可能为 list 或 tuple
    if "estimated_price_range" in data and isinstance(data["estimated_price_range"], list):
        data["estimated_price_range"] = tuple(data["estimated_price_range"])

    if "fair_value_range" in data and isinstance(data["fair_value_range"], list):
        data["fair_value_range"] = tuple(data["fair_value_range"])

    try:
        return AnalysisResult.model_validate(data)
    except ValidationError as e:
        logger.error(f"LLM输出校验失败: {e}")
        raise ValueError(f"LLM输出格式不符合要求: {e}")


def parse_with_retry(raw_text: str, llm_client=None, messages: list[dict] | None = None) -> AnalysisResult:
    """Parse LLM output, retrying once via the LLM if the first parse fails.

    Param:
        raw_text: raw LLM response text to parse
        llm_client: optional LLM client used for a single repair retry
        messages: optional original message list for the retry context
    Return:
        validated AnalysisResult from the original or repaired response
    """
    try:
        return parse_analysis_response(raw_text)
    except ValueError as e:
        if llm_client is None or messages is None:
            raise

        logger.info("首次解析失败，尝试一次修复重试...")
        retry_messages = messages + [
            {"role": "assistant", "content": raw_text},
            {
                "role": "user",
                "content": f"你的输出格式有误：{e}\n请严格按要求的JSON格式重新输出，不要添加任何额外文本。",
            },
        ]

        try:
            fixed_text = llm_client.chat(retry_messages, json_format=True)
            return parse_analysis_response(fixed_text)
        except Exception:
            logger.error("修复重试也失败，返回原始错误")
            raise
