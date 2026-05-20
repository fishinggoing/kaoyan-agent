"""Tests for collector module."""
import sqlite3
import json
from unittest.mock import patch, MagicMock
from kaoyan_agent.db.schema import create_tables
from kaoyan_agent.collector.base import WebCollector, CollectResult
from kaoyan_agent.collector.tools import execute_collect_tool


def test_collect_result_defaults():
    result = CollectResult(success=False)
    assert result.success is False
    assert result.schools_added == 0
    assert result.majors_added == 0
    assert result.scores_added == 0
    assert result.errors == []


def test_web_collector_initializes():
    conn = sqlite3.connect(":memory:")
    collector = WebCollector(conn)
    assert collector.conn is conn
    assert collector.client is not None
    collector.close()


def test_execute_collect_tool_bad_tool():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    result = execute_collect_tool(conn, None, "nonexistent", {})
    data = json.loads(result)
    assert "error" in data or "Unknown" in str(data)


def test_collector_module_imports():
    from kaoyan_agent.collector.yanzhao import YanZhaoCollector
    from kaoyan_agent.collector.parser import parse_with_claude
    from kaoyan_agent.agent.tools import TOOLS

    tool_names = [t["name"] for t in TOOLS]
    assert "collect_school_info" in tool_names
