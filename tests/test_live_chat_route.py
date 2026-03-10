from astrbot.dashboard.routes.tool_call_accumulator import accumulate_tool_call_part


def test_accumulate_tool_call_part_keeps_original_behavior_without_final_flag():
    tool_calls = {}
    accumulated_parts = []

    handled = accumulate_tool_call_part(
        tool_calls,
        accumulated_parts,
        "tool_call",
        '{"id":"call_1","name":"weather","args":{"city":"Tokyo"},"ts":1}',
    )
    assert handled is True
    assert "call_1" in tool_calls

    handled = accumulate_tool_call_part(
        tool_calls,
        accumulated_parts,
        "tool_call_result",
        '{"id":"call_1","result":"sunny","ts":2}',
    )
    assert handled is True
    assert tool_calls == {}
    assert accumulated_parts == [
        {
            "type": "tool_call",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "weather",
                    "args": {"city": "Tokyo"},
                    "ts": 1,
                    "result": "sunny",
                    "finished_ts": 2,
                }
            ],
        }
    ]


def test_accumulate_tool_call_part_ignores_non_final_tool_result():
    tool_calls = {
        "call_1": {
            "id": "call_1",
            "name": "openai_code_interpreter",
            "args": {},
            "ts": 1,
        }
    }
    accumulated_parts = []

    handled = accumulate_tool_call_part(
        tool_calls,
        accumulated_parts,
        "tool_call_result",
        '{"id":"call_1","result":"{\\"status\\":\\"interpreting\\"}","ts":2,"final":false}',
    )

    assert handled is True
    assert tool_calls == {
        "call_1": {
            "id": "call_1",
            "name": "openai_code_interpreter",
            "args": {},
            "ts": 1,
            "result": '{"status":"interpreting"}',
        }
    }
    assert accumulated_parts == []
