"""运行时、缓存、路径与账号安全配置分组。"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from app.configuration.groups.base import ConfigGroup
from app.configuration.locations import BACKEND_DIR


class RuntimeGroup(ConfigGroup):
    """缓存、路径、量化策略、Chat 能力与登录安全。"""

    PREFIX = ""

    # 缓存 TTL 必须为正整数：TTLCache.set 对 ttl<=0 直接抛 ValueError，
    # 零值配置若在启动时不拦截，会在运行时把对应接口全部打挂
    cache_ttl_analysis: int = Field(default=14400, ge=1)
    analysis_page_section_timeout_seconds: float = Field(default=15.0, gt=0)
    market_statistics_section_timeout_seconds: float = Field(default=15.0, gt=0)
    app_data_dir: Path = BACKEND_DIR / "data"
    portfolio_quote_cache_ttl_seconds: int = Field(default=10, ge=1)
    portfolio_quote_stale_ttl_seconds: int = Field(default=300, ge=1)
    update_hub_namespace: str = "fengliu1989"
    update_hub_repo: str = "a-share-backend"
    quant_strategy_dir: Path = BACKEND_DIR / "app" / "modules" / "quant" / "strategies" / "definitions"
    quant_strategy_reload_seconds: float = Field(default=5.0, ge=1.0, le=3600.0)
    # 产业链知识库外部导入目录：与用户存档根目录（data/industry_chains）分离，
    # 避免存档目录树被知识库 loader 的 glob 误扫
    industry_atlas_import_dir: Path = BACKEND_DIR / "data" / "industry_atlas_imports"
    # AI 产业链分析完成后是否自动挖掘进知识库（同名链稳定覆盖）
    industry_atlas_auto_mining: bool = True

    multi_agent_enabled: bool = True
    disabled_chat_skills: list[str] = Field(default_factory=list)
    disabled_chat_agents: list[str] = Field(default_factory=list)
    metrics_api_key: str = ""
    config_encryption_key: str = ""
    config_encryption_previous_keys: str = ""

    login_max_failures: int = 5
    login_window_seconds: int = 300
    login_lock_seconds: int = 300
    trust_proxy_headers: bool = False
    auth_cookie_secure: bool = False
    default_admin_username: str = "admin"
    default_admin_password: str = ""
