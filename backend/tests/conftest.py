"""跨测试文件共享的 fixture。"""

import pytest


@pytest.fixture
def application_handlers(monkeypatch):
    """安装真实 Application Tool handler，并在测试后还原模块级全局。

    ``configure_application_tools`` 写的是 ``app.agentic.tools.application._handlers``
    且没有任何恢复机制。不还原的话，依赖「handlers 未配置 -> RuntimeError」的断言
    会随测试执行顺序漂移，失败归因也变得困难。
    """
    from app.agentic.tools import application
    from app.runtime.agentic_tools import configure_application_tools

    monkeypatch.setattr(application, "_handlers", application._handlers, raising=False)
    configure_application_tools()
    return application.get_application_tool_handlers()
