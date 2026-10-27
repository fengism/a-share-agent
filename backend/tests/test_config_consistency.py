"""配置一致性守卫。

配置散落在 ``.env.example`` / ``Settings`` / ``ConfigUpdateRequest`` 三处，
本测试把三者的对应关系固定下来，任何新增字段或改默认值若未同步都会被拦住：

1. API 可编辑字段集合与 ``Settings`` / ``ConfigResponse`` 严格一致；
2. ``.env.example`` 的每个键都能映射到 ``Settings``（或已登记的非 Settings 键）；
3. API 可编辑字段在 ``.env.example`` 中都有文档条目；
4. ``.env.example`` 的取值与 schema 默认值一致，除非显式登记为部署差异。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.configuration import (
    CONFIG_VALUE_FIELDS,
    GLOBAL_SYNCED_KEYS,
    PERSISTED_GLOBAL_KEYS,
    PRIVATE_USER_KEYS,
    SECRET_KEYS,
    Settings,
)
from app.configuration.api_models import ConfigResponse, ConfigUpdateRequest
from app.configuration.effective import overlay_private
from app.configuration.groups import CONFIG_GROUPS

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"

# .env.example 中由 Docker Compose / os.getenv / 运维脚本消费，而非 Settings 的键。
NON_SETTINGS_ENV_KEYS = frozenset(
    {
        "APP_EXPOSE_DOCS",  # app/runtime/app_setup.py
        "NBSC_DATA_URL",  # infrastructure/providers/nbs.py
        "SESSION_TTL_DAYS",  # 仅出现在注释中的代码常量说明
        "TZ",
        "DOCKER_FRONTEND_PORT",
        "DOCKER_FRONTEND_BIND_ADDRESS",
        "DOCKER_SOCKET",
        "QUANT_STRATEGY_HOST_DIR",
        "BACKEND_IMAGE",
        "FRONTEND_IMAGE",
        "PYTHON_SANDBOX_DOCKER_SOCKET",
    }
)

# 部署模板刻意与 schema 默认值不同的项：模板是面向用户的推荐值，schema 是代码兜底。
INTENTIONAL_DEFAULT_OVERRIDES = {
    # 模板给更宽松的网络超时，避免弱网环境下 TDX 探测频繁超时
    "tdxhub_timeout_seconds",
    # 模板给更保守的东财冷却，降低被封 IP 的概率
    "eastmoney_cooldown_seconds",
    # 未配置凭证时不默认启用飞书文档转存
    "feishu_enabled",
    # 本地开发常需走系统代理
    "http_trust_env",
    # 大库占磁盘，模板默认少留一份（README 同步说明）
    "database_backup_retention_count",
}


def _parse_env_example() -> dict[str, str]:
    """解析所有 KEY=VALUE（含注释掉的示例键），值取首次出现。"""
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#?\s*([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if not match:
            continue
        values.setdefault(match.group(1), match.group(2).strip())
    return values


def _active_env_values() -> dict[str, str]:
    """仅解析未注释的 KEY=VALUE（真正会被 shell/docker 读取的项）。"""
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def _normalize(value):
    text = value.strip().strip('"').strip("'")
    return text


def test_api_fields_match_settings_and_response() -> None:
    # 每个接口字段都必须真实存在于 Settings，否则 setattr 会静默失败
    missing = sorted(CONFIG_VALUE_FIELDS - set(Settings.model_fields))
    assert not missing, f"ConfigUpdateRequest 存在 Settings 未定义字段: {missing}"

    assert set(ConfigResponse.model_fields) == CONFIG_VALUE_FIELDS | {
        "provider_defaults",
        "is_admin",
        # 只读派生字段：哪些私密项仍继承全局（管理员）配置，供前端标注「使用管理员配置」
        "inherited_keys",
    }
    assert set(ConfigUpdateRequest.model_fields) == CONFIG_VALUE_FIELDS


def test_scope_partitions_are_disjoint_and_total() -> None:
    assert PRIVATE_USER_KEYS & PERSISTED_GLOBAL_KEYS == frozenset()
    assert PRIVATE_USER_KEYS | PERSISTED_GLOBAL_KEYS == CONFIG_VALUE_FIELDS
    # 只有 private 字段需要（也才允许）同步到全局基线
    assert GLOBAL_SYNCED_KEYS <= PRIVATE_USER_KEYS
    # 敏感字段必须是真实配置项
    assert SECRET_KEYS <= set(Settings.model_fields)


def test_groups_cover_all_settings_fields() -> None:
    covered = [name for group in CONFIG_GROUPS for name in group.model_fields]
    assert len(covered) == len(set(covered)), "同一字段不得在多个分组重复声明"
    assert set(covered) == set(Settings.model_fields)


def test_group_view_reads_and_writes_flat_fields() -> None:
    settings = Settings()
    settings.llm.provider = "openai"
    assert settings.llm_provider == "openai"
    assert settings.llm.provider == "openai"
    settings.llm_provider = "deepseek"
    assert settings.llm.provider == "deepseek"
    # 组内无统一前缀的字段按原名访问
    settings.push.feishu_webhook_url = "https://example.invalid/hook"
    assert settings.feishu_webhook_url == "https://example.invalid/hook"
    with pytest.raises(AttributeError):
        settings.llm.not_a_real_field


def test_overlay_private_rejects_invalid_enum_value() -> None:
    """非法存量枚举值不得静默进入生效配置。"""
    base = Settings(llm_api_mode="auto")
    # model_copy(update=...) 不触发校验，必须由 coerce_setting_value 拦住
    merged = overlay_private(base, {"llm_api_mode": "bogus"})
    assert merged.llm_api_mode == "auto"

    merged_ok = overlay_private(base, {"llm_api_mode": "litellm"})
    assert merged_ok.llm_api_mode == "litellm"


def test_env_example_keys_are_known() -> None:
    env_keys = set(_parse_env_example())
    unknown = sorted(
        key
        for key in env_keys
        if key.lower() not in Settings.model_fields and key not in NON_SETTINGS_ENV_KEYS
    )
    assert not unknown, f".env.example 存在无效键（拼写错误或已废弃）: {unknown}"


# 少数字段刻意不写入 .env.example（例如仅内部派生）。目前为空，新增时须注明原因。
UNDOCUMENTED_ENV_FIELDS: frozenset[str] = frozenset()


def test_all_settings_fields_are_documented() -> None:
    """每个 Settings 字段都应在 .env.example 有对应条目（注释形式也算）。

    避免出现“只能改代码”的配置项，也避免新增字段忘了同步部署模板。
    """
    env_keys = set(_parse_env_example())
    undocumented = sorted(
        name
        for name in Settings.model_fields
        if name.upper() not in env_keys and name not in UNDOCUMENTED_ENV_FIELDS
    )
    assert not undocumented, f"以下配置项缺少 .env.example 文档: {undocumented}"


def test_env_example_values_match_schema_defaults() -> None:
    env_values = _active_env_values()
    mismatches: list[str] = []
    for key, raw in env_values.items():
        name = key.lower()
        field = Settings.model_fields.get(name)
        if field is None or name in INTENTIONAL_DEFAULT_OVERRIDES:
            continue
        default = field.get_default(call_default_factory=True)
        if default is None or isinstance(default, Path):
            continue
        text = _normalize(raw)
        if isinstance(default, bool):
            expected: object = text.lower() in ("1", "true", "yes", "on")
        elif isinstance(default, int):
            try:
                expected = int(text)
            except ValueError:
                mismatches.append(f"{key}={raw!r} 不是整数（schema 默认 {default!r}）")
                continue
        elif isinstance(default, float):
            try:
                expected = float(text)
            except ValueError:
                mismatches.append(f"{key}={raw!r} 不是数字（schema 默认 {default!r}）")
                continue
        elif isinstance(default, list):
            try:
                expected = json.loads(text)
            except json.JSONDecodeError:
                mismatches.append(f"{key}={raw!r} 不是 JSON 数组（schema 默认 {default!r}）")
                continue
        else:
            expected = text
        if expected != default:
            mismatches.append(f"{key}: env={raw!r} schema={default!r}")
    assert not mismatches, (
        "以下 .env.example 取值与 schema 默认不一致；"
        "如属刻意部署差异请加入 INTENTIONAL_DEFAULT_OVERRIDES 并注明原因:\n"
        + "\n".join(mismatches)
    )
