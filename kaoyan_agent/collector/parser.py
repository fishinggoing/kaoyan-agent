# kaoyan_agent/collector/parser.py
import json
import re
from anthropic import Anthropic


PARSE_PROMPT = """你是一个数据提取专家。从下面的网页内容中提取研究生招生相关信息。

请提取以下信息，返回严格的 JSON 格式（不要包含其他文字）：

{
  "schools": [
    {
      "name": "学校全称",
      "tier": "985/211/双一流/双非",
      "province": "省份",
      "city": "城市",
      "type": "综合/理工/师范/财经/医药/农林/政法/其他"
    }
  ],
  "majors": [
    {
      "school_name": "对应学校全称",
      "name": "专业名称",
      "discipline_rank": "学科评估等级（如A+/A/B+，没有则为空字符串）",
      "exam_subjects": ["科目1", "科目2", "科目3", "科目4"]
    }
  ],
  "admission_scores": [
    {
      "school_name": "学校全称",
      "major_name": "专业名称",
      "year": 年份数字,
      "admission_line": 复试线分数,
      "applicants": 报考人数,
      "enrolled": 录取人数,
      "push_free_ratio": 推免比例（0-1的小数）
    }
  ],
  "employment": [
    {
      "school_name": "学校全称",
      "year": 年份,
      "employment_rate": 就业率（0-1的小数）,
      "avg_salary": 平均薪资数字,
      "summary": "就业去向描述"
    }
  ]
}

规则：
1. 只提取页面中实际存在的信息，没有的字段用 null
2. 学校名称使用标准全称（如"浙江大学"而非"浙大"）
3. 如果页面没有某些类型的数据（如就业信息），对应数组可以为空 []
4. 分数、人数等数字字段必须是数字类型，不要带文字"""


def parse_with_claude(client: Anthropic, html: str, url: str = "") -> dict:
    """Use Claude to extract structured data from HTML content."""
    # Truncate HTML to avoid token limits (keep first 100K chars)
    truncated = html[:100000]

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=PARSE_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"请从以下网页内容提取招生数据（来源: {url}）：\n\n{truncated}"
            }
        ],
    )

    text = message.content[0].text

    # Extract JSON from response (Claude may wrap it in markdown code blocks)
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        text = json_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object directly
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group(0))
        return {"schools": [], "majors": [], "admission_scores": [], "employment": [],
                "_parse_error": text[:500]}
