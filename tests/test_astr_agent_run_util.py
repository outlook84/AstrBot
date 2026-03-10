import pytest

import astrbot.core.message.components as Comp
from astrbot.core.agent.response import AgentResponseData
from astrbot.core.agent.runners.base import AgentResponse
from astrbot.core.astr_agent_run_util import (
    _build_native_tool_result_display,
    run_agent,
)
from astrbot.core.message.message_event_result import MessageChain


def test_build_native_tool_result_display_for_code_interpreter():
    tool_name_by_call_id = {"ci_1": "openai_code_interpreter"}
    msg_chain = MessageChain(
        type="tool_call_result",
        chain=[
            Comp.Json(
                data={
                    "id": "ci_1",
                    "result": (
                        '{"status":"completed","logs":["hello\\n"],'
                        '"images":["https://example.com/result.png"]}'
                    ),
                }
            )
        ],
    )

    handled, display_chain = _build_native_tool_result_display(
        msg_chain,
        tool_name_by_call_id,
    )

    assert handled is True
    assert display_chain is not None
    assert len(display_chain.chain) == 2
    assert isinstance(display_chain.chain[0], Comp.Plain)
    assert "openai_code_interpreter" in display_chain.chain[0].text
    assert "hello" in display_chain.chain[0].text
    assert isinstance(display_chain.chain[1], Comp.Image)
    assert display_chain.chain[1].file == "https://example.com/result.png"
    assert tool_name_by_call_id == {}


def test_build_native_tool_result_display_suppresses_image_generation_status():
    tool_name_by_call_id = {"img_1": "openai_image_generation"}
    msg_chain = MessageChain(
        type="tool_call_result",
        chain=[
            Comp.Json(
                data={
                    "id": "img_1",
                    "result": '{"status":"completed","has_image":true}',
                }
            )
        ],
    )

    handled, display_chain = _build_native_tool_result_display(
        msg_chain,
        tool_name_by_call_id,
    )

    assert handled is True
    assert display_chain is None
    assert tool_name_by_call_id == {}


def test_build_native_tool_result_display_shows_image_generation_failure():
    tool_name_by_call_id = {"img_1": "openai_image_generation"}
    msg_chain = MessageChain(
        type="tool_call_result",
        chain=[
            Comp.Json(
                data={
                    "id": "img_1",
                    "result": '{"status":"failed","has_image":false}',
                }
            )
        ],
    )

    handled, display_chain = _build_native_tool_result_display(
        msg_chain,
        tool_name_by_call_id,
    )

    assert handled is True
    assert display_chain is not None
    assert len(display_chain.chain) == 1
    assert isinstance(display_chain.chain[0], Comp.Plain)
    assert "openai_image_generation" in display_chain.chain[0].text
    assert "failed" in display_chain.chain[0].text
    assert tool_name_by_call_id == {}


class _FakeTrace:
    def record(self, *args, **kwargs):
        return None


class _FakeEvent:
    def __init__(self):
        self.sent = []
        self.trace = _FakeTrace()
        self._extras = {}

    def is_stopped(self):
        return False

    def get_extra(self, key, default=None):
        return self._extras.get(key, default)

    def set_extra(self, key, value):
        self._extras[key] = value

    def get_platform_id(self):
        return "telegram"

    def get_platform_name(self):
        return "telegram"

    async def send(self, chain):
        self.sent.append(chain)

    def set_result(self, result):
        self.result = result

    def clear_result(self):
        self.result = None


class _FakeRunContext:
    def __init__(self, event):
        self.context = type("Ctx", (), {"event": event})()


class _FakeAgentRunner:
    def __init__(self, event, responses):
        self.run_context = _FakeRunContext(event)
        self._responses = responses
        self.streaming = True
        self.req = None

    async def step(self):
        for response in self._responses:
            yield response

    def done(self):
        return True

    def request_stop(self):
        return None


@pytest.mark.asyncio
async def test_run_agent_deduplicates_native_tool_call_status_messages():
    event = _FakeEvent()
    responses = [
        AgentResponse(
            type="tool_call",
            data=AgentResponseData(
                chain=MessageChain(
                    type="tool_call",
                    chain=[
                        Comp.Json(
                            data={
                                "id": "ci_1",
                                "name": "openai_code_interpreter",
                                "args": {},
                                "ts": 1.0,
                            }
                        )
                    ],
                )
            ),
        ),
        AgentResponse(
            type="tool_call",
            data=AgentResponseData(
                chain=MessageChain(
                    type="tool_call",
                    chain=[
                        Comp.Json(
                            data={
                                "id": "ci_1",
                                "name": "openai_code_interpreter",
                                "args": {"code": "print('hello')"},
                                "ts": 2.0,
                            }
                        )
                    ],
                )
            ),
        ),
    ]
    runner = _FakeAgentRunner(event, responses)

    yielded = []
    async for item in run_agent(
        runner,
        max_step=1,
        show_tool_use=True,
        show_tool_call_result=False,
    ):
        yielded.append(item)

    sent_texts = [
        chain.chain[0].text
        for chain in event.sent
        if chain.chain and isinstance(chain.chain[0], Comp.Plain)
    ]
    assert len(sent_texts) == 1
    assert "openai_code_interpreter" in sent_texts[0]
    assert len(yielded) == 2


@pytest.mark.asyncio
async def test_run_agent_streaming_keeps_final_image_components():
    event = _FakeEvent()
    responses = [
        AgentResponse(
            type="streaming_delta",
            data=AgentResponseData(chain=MessageChain().message("Generated image")),
        ),
        AgentResponse(
            type="llm_result",
            data=AgentResponseData(
                chain=MessageChain(
                    chain=[
                        Comp.Plain("Generated image"),
                        Comp.Image.fromBase64("aGVsbG8="),
                    ]
                )
            ),
        ),
    ]
    runner = _FakeAgentRunner(event, responses)

    yielded = []
    async for item in run_agent(
        runner,
        max_step=1,
        show_tool_use=True,
        show_tool_call_result=False,
    ):
        yielded.append(item)

    assert len(yielded) == 2
    assert isinstance(yielded[0].chain[0], Comp.Plain)
    assert len(yielded[1].chain) == 1
    assert isinstance(yielded[1].chain[0], Comp.Image)
    assert yielded[1].chain[0].file == "base64://aGVsbG8="
