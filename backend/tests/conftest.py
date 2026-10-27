import os

# 为测试环境兜底提供合法 32 字节 Base64 密钥，避免 CI / 无 .env 环境下敏感配置读写抛 ConfigEncryptionError
if not os.environ.get("CONFIG_ENCRYPTION_KEY"):
    os.environ["CONFIG_ENCRYPTION_KEY"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

import pytest

from app.infrastructure.persistence import init_db
from app.infrastructure.persistence.connection import reset_for_tests


@pytest.fixture(scope="session", autouse=True)
def _schema_ready():
    """会话级建表一次。

    reset_for_tests() 只关连接并重置迁移标记，不会建表；CI 上数据库是全新的，
    必须先跑一次 init_db() 让表结构存在，否则会报 "no such table"。
    建表本身很快（~0.4s），但对每个用例都跑会拖慢整轮，故只在会话开始时执行一次。
    """
    reset_for_tests()
    init_db()
    yield
