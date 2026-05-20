import os
import sqlite3
import json
from anthropic import Anthropic
from kaoyan_agent.db.schema import create_tables
from kaoyan_agent.agent.dialogue import run_agent, execute_tool


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("请设置 ANTHROPIC_API_KEY 环境变量")
        return

    client = Anthropic(api_key=api_key)
    conn = sqlite3.connect("kaoyan.db")
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    # 检查是否需要导入种子数据
    cursor = conn.execute("SELECT COUNT(*) FROM schools")
    if cursor.fetchone()[0] == 0:
        print("数据库为空，正在导入种子数据...")
        from kaoyan_agent.seed_data import seed
        seed(conn)

    print("=" * 50)
    print("  考研择校助手")
    print("  可以问我：'帮我推荐学校' 或 '浙大计算机怎么样'")
    print("  输入 /quit 退出")
    print("=" * 50)

    messages = []
    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("再见！")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            result = run_agent(client, conn, messages)

            if result["text"]:
                print(f"\n助手: {result['text']}")

            if result["stop_reason"] == "end_turn":
                messages.append({"role": "assistant", "content": result["text"]})
                break

            if result["stop_reason"] == "tool_use":
                tool_content = []
                for tc in result["tool_calls"]:
                    tool_result = execute_tool(conn, tc["name"], tc["input"])
                    print(f"\n[查询: {tc['name']}]")
                    tool_content.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": tool_result,
                        }
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            *[
                                {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": tc["input"],
                                }
                                for tc in result["tool_calls"]
                            ],
                            *(
                                [{"type": "text", "text": result["text"]}]
                                if result["text"]
                                else []
                            ),
                        ],
                    }
                )
                messages.append({"role": "user", "content": tool_content})

    conn.close()


if __name__ == "__main__":
    main()
