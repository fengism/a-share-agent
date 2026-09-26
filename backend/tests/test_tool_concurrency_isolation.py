"""工具并发隔离的回归护栏。

四类「同一次执行被算错」的问题：

1. 共享 future 由发起者取消 -> 等待者收到 CancelledError，它自己完全没被取消。
   真实触发场景：客户端断连、外层 asyncio.timeout、plan 层批量 cancel。
2. 信号量排队时间被计入工具超时 -> 一次都没执行却报「执行超时 + 可重试」，
   模型原样再调一次、又排一次队。max_parallel_calls 是进程级共享的。
3. 缓存/in-flight 命中仍然扣预算：1 次真实执行、2 次额度扣减。
4. plan 执行循环里「死任务」残留 -> 整个请求挂到外层 300s 超时并占满并发额度。
"""
import asyncio
import json

import pytest

from app.agentic.agents.contracts import AgentProfile
from app.agentic.catalog import registry
from app.agentic.events import _tool_result_summary
from app.agentic.orchestration.contracts import AgentTask, ExecutionPlan
from app.agentic.orchestration.executor import stream_execution_plan
from app.agentic.protocol import ToolCallInfo
from app.agentic.runtime.context import AgentExecutionContext
from app.agentic.tools.cache import SharedToolCache
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.configuration.schema import Settings

_EXECUTION_COUNT: dict[str, int] = {}
_CANCELLED: list[str] = []


def _register(name: str, executor, **policy_kwargs) -> Tool:
    _EXECUTION_COUNT[name] = 0
    tool = Tool(
        name=name,
        description="测试用",
        parameters={"type": "object", "properties": {}},
        executor=executor,
        policy=ToolPolicy(**policy_kwargs),
    )
    registry.register_tool(tool)
    return tool


@pytest.fixture
def registry_guard():
    added: list[str] = []

    def register(name: str, executor, **policy_kwargs) -> Tool:
        added.append(name)
        return _register(name, executor, **policy_kwargs)

    yield register
    for name in added:
        registry._tools.pop(name, None)
        _EXECUTION_COUNT.pop(name, None)


def _call(name: str, call_id: str = "c1") -> ToolCallInfo:
    return ToolCallInfo(id=call_id, function={"name": name, "arguments": "{}"})


def _error_code(result) -> str:
    return json.loads(result.content)["error"]["code"]


class TestSharedCallSurvivesInitiatorCancellation:
    async def test_waiter_still_gets_the_result(self, registry_guard):
        async def slow() -> dict:
            _EXECUTION_COUNT["stub_share_cancel"] += 1
            try:
                await asyncio.sleep(0.6)
            except asyncio.CancelledError:
                _CANCELLED.append("stub_share_cancel")
                raise
            return {"v": 1}

        registry_guard("stub_share_cancel", slow)

        async def scenario() -> None:
            cache = SharedToolCache()
            initiator = asyncio.create_task(cache.execute(_call("stub_share_cancel", "c1")))
            await asyncio.sleep(0.1)
            waiter = asyncio.create_task(cache.execute(_call("stub_share_cancel", "c2")))
            await asyncio.sleep(0.1)
            initiator.cancel()
            with pytest.raises(asyncio.CancelledError):
                await initiator
            # 等待者自己完全没被取消，却因为发起者被取消而收到 CancelledError。
            result = await asyncio.wait_for(waiter, timeout=3)
            assert json.loads(result.content)["ok"] is True

        await scenario()
        assert _EXECUTION_COUNT["stub_share_cancel"] == 1
        assert _CANCELLED == []  # 共享工作本身不该被发起者的取消打断

    async def test_waiter_receives_the_real_error_not_cancellation(self, registry_guard):
        async def boom() -> dict:
            _EXECUTION_COUNT["stub_share_error"] += 1
            await asyncio.sleep(0.3)
            raise RuntimeError("上游挂了")

        registry_guard("stub_share_error", boom)

        cache = SharedToolCache()
        initiator = asyncio.create_task(cache.execute(_call("stub_share_error", "c1")))
        await asyncio.sleep(0.05)
        waiter = asyncio.create_task(cache.execute(_call("stub_share_error", "c2")))
        await asyncio.sleep(0.05)
        initiator.cancel()
        with pytest.raises(asyncio.CancelledError):
            await initiator
        # 等待者拿到的是同一份失败结果，而不是被发起者的取消牵连成 CancelledError。
        result = await asyncio.wait_for(waiter, timeout=3)
        assert result.is_error is True
        assert json.loads(result.content)["error"]["code"] == "execution_failed"
        assert _EXECUTION_COUNT["stub_share_error"] == 1

    async def test_failed_call_is_not_readable_from_cache(self, registry_guard):
        async def boom() -> dict:
            raise RuntimeError("挂了")

        registry_guard("stub_share_failed_entry", boom)
        cache = SharedToolCache()
        result = await cache.execute(_call("stub_share_failed_entry"))
        # 失败必须已从缓存摘除，且读取路径不能把异常抛穿调用方。
        assert result.is_error is True
        assert cache.get_cached_result(_call("stub_share_failed_entry")) is None


class TestQueueWaitIsNotExecutionTimeout:
    async def test_second_call_reports_queue_timeout(self, registry_guard):
        async def hog() -> dict:
            _EXECUTION_COUNT["stub_queue"] += 1
            await asyncio.sleep(5)
            return {"v": 1}

        registry_guard("stub_queue", hog, timeout_seconds=2.0, max_parallel_calls=1)

        first, second = await asyncio.gather(
            registry.get_tool("stub_queue").execute(_call("stub_queue", "c1")),
            registry.get_tool("stub_queue").execute(_call("stub_queue", "c2")),
        )
        # 第一个真的执行了但超时；第二个一次都没执行，不能报「执行超时」。
        assert _error_code(first) == "timeout"
        assert _error_code(second) == "tool_queue_timeout"
        assert _EXECUTION_COUNT["stub_queue"] == 1

    async def test_queue_timeout_is_not_retryable(self, registry_guard):
        async def hog() -> dict:
            await asyncio.sleep(5)
            return {"v": 1}

        registry_guard("stub_queue_nr", hog, timeout_seconds=2.0, max_parallel_calls=1)
        results = await asyncio.gather(
            registry.get_tool("stub_queue_nr").execute(_call("stub_queue_nr", "c1")),
            registry.get_tool("stub_queue_nr").execute(_call("stub_queue_nr", "c2")),
        )
        payload = json.loads(results[1].content)
        assert payload["error"]["retryable"] is False
        assert "不要立刻重复调用" in payload["error"]["message"]
        assert _tool_result_summary(results[1]).summary == "工具并发额度已满，本次未执行"

    async def test_waiting_caller_still_executes_successfully(self, registry_guard):
        async def quick() -> dict:
            _EXECUTION_COUNT["stub_queue_ok"] += 1
            await asyncio.sleep(0.2)
            return {"v": 1}

        registry_guard("stub_queue_ok", quick, timeout_seconds=5.0, max_parallel_calls=1)
        first, second = await asyncio.gather(
            registry.get_tool("stub_queue_ok").execute(_call("stub_queue_ok", "c1")),
            registry.get_tool("stub_queue_ok").execute(_call("stub_queue_ok", "c2")),
        )
        # 排队等到了额度就必须真的执行，不能因为等过就判失败。
        assert first.is_error is False
        assert second.is_error is False
        assert _EXECUTION_COUNT["stub_queue_ok"] == 2


class TestSharedResultsDoNotDoubleCharge:
    async def test_waiter_is_flagged_shared_and_leader_is_not(self, registry_guard):
        async def quick() -> dict:
            _EXECUTION_COUNT["stub_charge"] += 1
            await asyncio.sleep(0.2)
            return {"v": 1}

        registry_guard("stub_charge", quick)
        cache = SharedToolCache()
        leader = asyncio.create_task(cache.execute_shared(_call("stub_charge", "c1")))
        await asyncio.sleep(0.05)
        waiter = asyncio.create_task(cache.execute_shared(_call("stub_charge", "c2")))
        leader_result, leader_shared = await leader
        waiter_result, waiter_shared = await waiter
        assert leader_shared is False
        assert waiter_shared is True
        assert leader_result.content == waiter_result.content
        assert _EXECUTION_COUNT["stub_charge"] == 1

    async def test_refund_restores_budget(self):
        context = AgentExecutionContext(settings=Settings(chat_max_tool_calls_total=4))
        assert await context.reserve_tool_calls(3) == 3
        assert context.tool_calls_remaining == 1
        assert await context.refund_tool_calls(1) == 1
        assert context.tool_calls_remaining == 2
        assert context.tool_calls_used == 2

    async def test_refund_never_goes_negative(self):
        context = AgentExecutionContext(settings=Settings(chat_max_tool_calls_total=4))
        assert await context.refund_tool_calls(3) == 0
        assert context.tool_calls_used == 0
        await context.reserve_tool_calls(1)
        assert await context.refund_tool_calls(5) == 1
        assert context.tool_calls_used == 0

    async def test_refund_returns_reserved_budget(self):
        context = AgentExecutionContext(
            settings=Settings(chat_max_tool_calls_total=10),
            reserved_tool_names=("web_search",),
            reserved_tool_calls=4,
        )
        await context.reserve_tool_calls(2, tool_name="web_search")
        assert context.reserved_calls_remaining == 2
        await context.refund_tool_calls(2)
        assert context.reserved_calls_remaining == 4

    async def test_refund_restores_search_pacing(self):
        from app.agentic.runtime.research_policy import ResearchSearchPolicy

        context = AgentExecutionContext(
            settings=Settings(chat_max_tool_calls_total=10),
            search_policy=ResearchSearchPolicy(
                tool_names=("web_search",), total_limit=4, burst_limit=2,
                read_tool_names=("web_fetch",),
            ),
        )
        await context.reserve_tool_calls(2, tool_name="web_search")
        assert context.search_policy.used == 2
        await context.refund_tool_calls(2)
        assert context.search_policy.used == 0
        assert context.search_policy.available == 2


def _profile(name: str) -> AgentProfile:
    return AgentProfile(
        name=name,
        display_name=name,
        description="测试用",
        system_prompt="测试用",
        tool_names=(),
    )


class TestExecutorRefundsSharedCalls:
    """端到端：1 次真实执行、2 个 agent 各发起一次，预算只能扣 1 次。

    同批内的重复调用已被批内去重挡住，所以这里必须用两个 agent 并发：第二个在
    「已决定执行」之后才发现结果由第一个的执行提供（in-flight 合并）。
    """

    async def test_concurrent_agents_charge_once_for_one_execution(self, registry_guard):
        import time

        from app.agentic.agents.contracts import AgentProfile
        from app.agentic.agents.executor import AgentExecutor, _ExecutionState
        from app.agentic.events import AgentEvent
        from app.infrastructure.llm.capabilities import DEFAULT_LLM_CAPABILITIES

        async def slow() -> dict:
            _EXECUTION_COUNT["stub_refund"] += 1
            await asyncio.sleep(0.3)
            return {"v": 1}

        registry_guard("stub_refund", slow)

        context = AgentExecutionContext(settings=Settings(chat_max_tool_calls_total=8))
        profile = AgentProfile(
            name="refund_tester",
            display_name="退款测试",
            description="测试",
            system_prompt="prompt",
            tool_names=("stub_refund",),
        )

        def new_state() -> "_ExecutionState":
            return _ExecutionState(
                started_at=time.monotonic(),
                messages=[],
                effective_tool_names=list(profile.tool_names),
                tool_definitions=[],
                tool_cache=context.tool_cache,
                max_tool_context_characters=8000,
            )

        async def emit(_event: AgentEvent) -> None:
            return None

        async def run(call_id: str) -> None:
            await AgentExecutor()._execute_tool_calls(
                profile,
                new_state(),
                [ToolCallInfo(id=call_id, function={"name": "stub_refund", "arguments": "{}"})],
                "",
                emit,
                context,
                0,
                DEFAULT_LLM_CAPABILITIES,
            )

        first = asyncio.create_task(run("a1"))
        await asyncio.sleep(0.05)
        second = asyncio.create_task(run("b1"))
        await asyncio.gather(first, second)

        assert _EXECUTION_COUNT["stub_refund"] == 1  # 只真实执行了一次
        assert context.tool_calls_used == 1  # 也只扣了一次
        assert context.tool_calls_remaining == 7


class TestPlanLoopRecoversFromDeadTasks:
    """被取消的任务不会发出 _TaskCompleted；它的 key 曾永久留在 running 里。"""

    @staticmethod
    def _drain(plan: ExecutionPlan) -> list:
        async def scenario() -> list:
            events = []
            generator = stream_execution_plan(
                agents={task.agent_name: _profile(task.agent_name) for task in plan.tasks},
                plan=plan,
                message="目标",
                history=None,
                llm_client=None,  # type: ignore[arg-type]
                model="test-model",
                results={},
            )
            async for event in generator:
                events.append(event)
            return events

        # 修复前这里会一直等在 queue.get() 上，只能靠外层 300s 超时收场。
        return asyncio.wait_for(scenario(), timeout=5)

    @staticmethod
    def _steps(events: list) -> list:
        return [event.plan_step for event in events if event.plan_step is not None]

    @pytest.fixture(autouse=True)
    def _cancel_every_agent(self, monkeypatch):
        async def cancelled(*_args, **_kwargs):
            raise asyncio.CancelledError

        monkeypatch.setattr(
            "app.agentic.orchestration.executor.agent_executor.run", cancelled
        )

    async def test_single_cancelled_task_terminates(self):
        plan = ExecutionPlan(
            tasks=(
                AgentTask(
                    task_id="t1",
                    agent_name="alpha",
                    display_name="甲",
                    objective="分析甲",
                    allowed_tools=(),
                ),
            )
        )
        steps = self._steps(await self._drain(plan))
        # 关键是「能终止」：修复前这里会挂到外层 300s 超时。
        assert any(step.status == "failed" for step in steps), steps

    async def test_dependent_task_is_failed_not_hung(self):
        plan = ExecutionPlan(
            tasks=(
                AgentTask(
                    task_id="t1",
                    agent_name="alpha",
                    display_name="甲",
                    objective="分析甲",
                    allowed_tools=(),
                ),
                AgentTask(
                    task_id="t2",
                    agent_name="beta",
                    display_name="乙",
                    objective="分析乙",
                    allowed_tools=(),
                    dependencies=("t1",),
                ),
            )
        )
        steps = self._steps(await self._drain(plan))
        # 依赖方不能无限等一个已经死掉的前置任务。
        assert any(
            "前置分析未有效完成" in (step.detail or "") for step in steps
        ), [(step.step_id, step.status, step.detail) for step in steps]
