import json


def accumulate_tool_call_part(
    tool_calls: dict[str, dict],
    accumulated_parts: list[dict],
    chain_type: str | None,
    result_text: str,
) -> bool:
    if chain_type == "tool_call":
        tool_call = json.loads(result_text)
        tool_call_id = tool_call.get("id")
        if tool_call_id is None:
            return False
        tool_calls[str(tool_call_id)] = tool_call
        return True

    if chain_type == "tool_call_result":
        tcr = json.loads(result_text)
        tc_id = tcr.get("id")
        if tc_id is None:
            return False
        tc_id = str(tc_id)
        if tc_id not in tool_calls:
            return False
        tool_calls[tc_id]["result"] = tcr.get("result")
        if tcr.get("final", True):
            tool_calls[tc_id]["finished_ts"] = tcr.get("ts")
            accumulated_parts.append(
                {
                    "type": "tool_call",
                    "tool_calls": [tool_calls[tc_id]],
                }
            )
            tool_calls.pop(tc_id, None)
        return True

    return False
