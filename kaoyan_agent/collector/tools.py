# kaoyan_agent/collector/tools.py
import json
import sqlite3
from anthropic import Anthropic
from kaoyan_agent.collector.yanzhao import YanZhaoCollector


def execute_collect_tool(
    conn: sqlite3.Connection,
    client: Anthropic,
    tool_name: str,
    tool_input: dict,
) -> str:
    if tool_name == "collect_school_info":
        school_name = tool_input.get("school_name", "")
        collector = YanZhaoCollector(conn, client)
        result = collector.collect_school_info(school_name)
        collector.close()

        if result.success:
            return json.dumps(
                {
                    "status": "success",
                    "message": f"已采集{school_name}的数据：新增{result.schools_added}所学校、{result.majors_added}个专业、{result.scores_added}条分数线",
                    "schools_added": result.schools_added,
                    "majors_added": result.majors_added,
                    "scores_added": result.scores_added,
                },
                ensure_ascii=False,
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"采集{school_name}数据失败",
                    "errors": result.errors,
                },
                ensure_ascii=False,
                indent=2,
            )

    return json.dumps({"error": f"Unknown collector tool: {tool_name}"})
