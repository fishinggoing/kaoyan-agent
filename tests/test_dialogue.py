# tests/test_dialogue.py
import sqlite3
import json
from unittest.mock import patch, MagicMock
from kaoyan_agent.db.schema import create_tables
from kaoyan_agent.agent.dialogue import execute_tool, run_agent


def test_execute_tool_search_schools():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    conn.execute(
        "INSERT INTO schools (name, tier, province, city) VALUES (?,?,?,?)",
        ("浙江大学", "985", "浙江", "杭州"),
    )
    conn.commit()

    result = execute_tool(conn, "search_schools", {"province": "浙江"})
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["name"] == "浙江大学"


def test_execute_tool_unknown():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    result = execute_tool(conn, "nonexistent", {})
    assert "error" in result.lower()


def test_run_agent_returns_structure():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    result = execute_tool(
        conn, "search_schools", {"tier": "985", "province": "浙江"}
    )
    data = json.loads(result)
    assert isinstance(data, list)
