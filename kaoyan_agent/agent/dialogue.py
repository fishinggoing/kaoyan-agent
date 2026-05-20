# kaoyan_agent/agent/dialogue.py
import json
import sqlite3
from anthropic import Anthropic
from kaoyan_agent.agent.tools import TOOLS
from kaoyan_agent.agent.prompts import SYSTEM_PROMPT
from kaoyan_agent.db import queries


def execute_tool(conn: sqlite3.Connection, tool_name: str, tool_input: dict) -> str:
    func_map = {
        "search_schools": queries.search_schools,
        "get_majors": queries.get_majors,
        "query_scores": queries.query_scores,
        "query_admitted_scores": queries.query_admitted_scores,
        "get_employment": queries.get_employment,
        "compare_schools": queries.compare_schools,
    }
    func = func_map.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    result = func(conn, **tool_input)
    return json.dumps(result, ensure_ascii=False, indent=2)


def run_agent(
    client: Anthropic,
    conn: sqlite3.Connection,
    messages: list[dict],
) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    text = ""
    tool_calls = []

    for block in response.content:
        if block.type == "text":
            text += block.text
        elif block.type == "tool_use":
            tool_calls.append(
                {
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input),
                }
            )

    return {
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": response.stop_reason,
    }
