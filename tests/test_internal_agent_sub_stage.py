import astrbot.core.message.components as Comp
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.pipeline.process_stage.method.agent_sub_stages.internal import (
    _select_final_stream_result_chain,
)
from astrbot.core.provider.entities import LLMResponse


def test_select_final_stream_result_chain_prefers_result_chain_with_image():
    llm_response = LLMResponse(
        role="assistant",
        completion_text="plain text fallback",
        result_chain=MessageChain(
            chain=[
                Comp.Plain("Generated image"),
                Comp.Image.fromURL("https://example.com/generated.png"),
            ]
        ),
    )

    chain = _select_final_stream_result_chain(llm_response)

    assert len(chain) == 2
    assert isinstance(chain[0], Comp.Plain)
    assert isinstance(chain[1], Comp.Image)


def test_select_final_stream_result_chain_falls_back_to_text():
    llm_response = LLMResponse(
        role="assistant",
        completion_text="text only",
    )

    chain = _select_final_stream_result_chain(llm_response)

    assert len(chain) == 1
    assert isinstance(chain[0], Comp.Plain)
    assert chain[0].text == "text only"


def test_select_final_stream_result_chain_keeps_plain_text_only_result_chain_behavior():
    llm_response = LLMResponse(
        role="assistant",
        completion_text="plain text fallback",
        result_chain=MessageChain(
            chain=[
                Comp.Plain("plain text fallback"),
            ]
        ),
    )

    chain = _select_final_stream_result_chain(llm_response)

    assert len(chain) == 1
    assert isinstance(chain[0], Comp.Plain)
    assert chain[0].text == "plain text fallback"
