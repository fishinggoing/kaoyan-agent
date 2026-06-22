"""
Orchestrator Agent — produces comprehensive school/major recommendations.

Flow:
1. Accept user profile + preferences
2. Query DB for matching schools + score line data
3. Synthesize ranked recommendations via DeepSeek
"""

import json
import re
import logging
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

RECOMMEND_SYSTEM_PROMPT = """你是一位资深的考研择校顾问专家。你将收到:
1. 考生基本信息（本科院校、专业、预估分数、目标省份、目标层次、考试科目配置、学科优劣势等）
2. 匹配的院校列表及其历年分数线数据
3. 分数线趋势分析

请综合分析以上数据，为考生提供科学的择校推荐。返回以下JSON格式:

{
  "recommendations": [
    {
      "school_name": "院校全称",
      "school_province": "所在省份",
      "school_level": "C9/985/211/军事院校/中外合作/双一流/普本",
      "major_name": "推荐专业",
      "major_code": "专业代码",
      "risk_level": "冲刺/稳妥/保底",
      "match_score": 85,
      "score_trend": "分数线趋势简述(50字)",
      "competition": "竞争程度简述(50字)",
      "pros": ["优势1", "优势2", "优势3"],
      "cons": ["劣势1", "劣势2"]
    }
  ],
  "analysis": "整体分析(200字内)，包括该考生的定位评估、竞争力分析、以及报考策略建议",
  "plan_suggestion": "备考建议(150字内)，基于该考生的可用时间和预估分数，给出初步的备考方向建议"
}

推荐规则:
- match_score 按综合匹配度(0-100)打分，考虑分数线匹配度、院校层次、地区偏好等
- risk_level: 如果预估分比近年复试线高15+分为"保底"，差值在±15分为"稳妥"，低15+分为"冲刺"
- 至少返回2条推荐，最多6条
- 推荐应覆盖不同风险等级
- 优先推荐目标省份的院校，其次推荐相邻省份
- 注意考生考试科目配置：如数学考数二/数三或不考数学，避免推荐要求数一的专业；英语考英二的避免推荐要求英一的院校
- 考虑学科优劣势：弱项科目对应专业要求高的应标注为更高风险；强项科目对应的专业方向可作为优势加分
- 每所学校携带 admissions_summary 字段，包含复试占比、是否保护一志愿、双非友好度。在 pros/cons 中务必提及：复试占比高的标注为风险(cons)，保护一志愿和不歧视双非的标注为优势(pros)，不保护一志愿或歧视双非的标注为劣势(cons)
"""


@dataclass
class RecommendationItem:
    school_name: str
    school_province: str
    school_level: str
    school_type: str = ""
    school_description: str = ""
    ranking_national: int | None = None
    major_name: str = ""
    major_code: str = ""
    risk_level: str = "稳妥"
    match_score: float = 0.0
    score_trend: str = ""
    competition: str = ""
    re_exam_avg_score: float = 0.0
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    subject_warnings: list[str] = field(default_factory=list)
    major_match_level: str = ""
    is_research_institute: bool = False
    major_strength_score: float = 50.0
    major_strength_label: str = ""
    admissions_summary: str = ""


@dataclass
class DecisionResult:
    recommendations: list[RecommendationItem]
    analysis: str
    plan_suggestion: str
    raw_text: str


ANALYZE_SYSTEM_PROMPT = """你是一位资深的考研择校顾问专家。你将收到一所具体院校和专业的详细信息，包括:
1. 院校基本信息（名称、省份、层次、类型）
2. 专业信息（名称、代码、学位类型）
3. 历年分数线数据

请为该院校+专业组合提供专业的择校分析。返回以下JSON格式:

{
  "risk_level": "冲刺/稳妥/保底",
  "match_score": 85,
  "score_trend": "分数线趋势简述(80字内)",
  "competition": "竞争程度分析(80字内)",
  "pros": ["优势1", "优势2", "优势3"],
  "cons": ["劣势1", "劣势2"],
  "analysis": "综合分析(200字内)，包括院校实力、专业前景、报考难度等",
  "preparation_tips": "备考建议(100字内)"
}

分析规则:
- match_score 按综合匹配度(0-100)打分
- risk_level: 如果预估分比近年复试线高15+分为"保底"，差值在±15分为"稳妥"，低15+分为"冲刺"
- 如无预估分数，基于院校层次和竞争程度给出相对难度评估
"""


@dataclass
class AnalyzeResult:
    risk_level: str
    match_score: float
    score_trend: str
    competition: str
    pros: list[str]
    cons: list[str]
    analysis: str
    preparation_tips: str
    raw_text: str


class OrchestratorAgent:
    """Multi-agent coordinator for grad school decision recommendations."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model

    async def recommend(
        self,
        profile: dict,
        matching_schools: list[dict],
        score_data: list[dict],
        trend_analyses: list[dict],
        exam_subjects_lookup: dict | None = None,
    ) -> DecisionResult:
        """Generate comprehensive school recommendations."""
        logger.info(
            f"Orchestrator: recommending for profile #{profile.get('id')}, "
            f"{len(matching_schools)} schools matched"
        )

        user_content = self._build_prompt(
            profile, matching_schools, score_data, trend_analyses, exam_subjects_lookup
        )

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": RECOMMEND_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.4,
                max_tokens=3000,
            )

            content = resp.choices[0].message.content or "{}"
            return self._parse_response(content)

        except Exception as e:
            logger.error(f"Orchestrator recommendation failed: {e}")
            return DecisionResult(
                recommendations=[],
                analysis="AI推荐服务暂时不可用，请稍后重试",
                plan_suggestion="",
                raw_text="",
            )

    def _build_prompt(
        self,
        profile: dict,
        schools: list[dict],
        score_data: list[dict],
        trends: list[dict],
        exam_subjects_lookup: dict | None = None,
    ) -> str:
        exam_config = profile.get("exam_config", {})
        strengths = profile.get("subject_strengths", {})

        profile_text = json.dumps(
            {
                "本科院校": profile.get("undergraduate_school", ""),
                "本科专业": profile.get("undergraduate_major", ""),
                "预估分数": profile.get("estimated_score", "未提供"),
                "目标省份": profile.get("target_province", "不限"),
                "目标层次": profile.get("target_level", "不限"),
                "考试科目": {
                    "数学": exam_config.get("math", "未填写"),
                    "英语": exam_config.get("english", "未填写"),
                    "政治": exam_config.get("politics", "政治"),
                    "专业课": exam_config.get("专业课", "未填写"),
                },
                "学科优劣势": strengths if strengths else "未填写",
                "每日可用时间": f"{profile.get('available_hours_per_day', '未知')}小时",
                "考试年份": profile.get("exam_year", ""),
                "备注": profile.get("notes", ""),
            },
            ensure_ascii=False,
            indent=2,
        )

        schools_text = json.dumps(
            [
                {
                    "name": s.get("name"),
                    "province": s.get("province"),
                    "level": s.get("level"),
                    "type": s.get("school_type"),
                    "description": (s.get("description") or "")[:100],
                }
                for s in schools[:15]
            ],
            ensure_ascii=False,
            indent=2,
        )

        trends_text = json.dumps(
            [
                {
                    "school": t.get("school_name"),
                    "major": t.get("major_name"),
                    "trend": t.get("trend_analysis", ""),
                }
                for t in trends[:10]
            ],
            ensure_ascii=False,
            indent=2,
        )

        score_text = json.dumps(
            [
                {k: v for k, v in s.items() if k not in ("id",)}
                for s in score_data[:30]
            ],
            ensure_ascii=False,
            indent=2,
        )

        exam_subjects_text = ""
        if exam_subjects_lookup:
            subjects_data = {}
            for (sid, mcode), subj in exam_subjects_lookup.items():
                key = f"{sid}:{mcode}"
                if isinstance(subj, str) and subj.startswith("["):
                    try:
                        subjects_data[key] = json.loads(subj)
                    except json.JSONDecodeError:
                        subjects_data[key] = subj
                else:
                    subjects_data[key] = subj
            exam_subjects_text = f"## 考试科目\n{json.dumps(subjects_data, ensure_ascii=False, indent=2)}\n\n"

        return (
            f"## 考生信息\n{profile_text}\n\n"
            f"## 匹配院校\n{schools_text}\n\n"
            f"## 历年分数线\n{score_text}\n\n"
            f"## 趋势分析\n{trends_text}\n\n"
            f"{exam_subjects_text}"
            "请基于以上数据给出择校推荐。"
        )

    def _parse_response(self, content: str) -> DecisionResult:
        data = _extract_json(content)
        if data is None:
            return DecisionResult(
                recommendations=[],
                analysis=content[:500],
                plan_suggestion="",
                raw_text=content,
            )

        recs = [
            RecommendationItem(
                school_name=r.get("school_name", ""),
                school_province=r.get("school_province", ""),
                school_level=r.get("school_level", ""),
                major_name=r.get("major_name", ""),
                major_code=r.get("major_code", ""),
                risk_level=r.get("risk_level", "稳妥"),
                match_score=float(r.get("match_score", 70)),
                score_trend=r.get("score_trend", ""),
                competition=r.get("competition", ""),
                pros=r.get("pros", []),
                cons=r.get("cons", []),
            )
            for r in data.get("recommendations", [])
        ]

        return DecisionResult(
            recommendations=recs,
            analysis=data.get("analysis", ""),
            plan_suggestion=data.get("plan_suggestion", ""),
            raw_text=content,
        )

    async def analyze_single(
        self,
        school: dict,
        major: dict,
        score_lines: list[dict],
        estimated_score: int | None = None,
    ) -> AnalyzeResult:
        """Analyze a single school + major combination."""
        logger.info(
            f"Orchestrator: analyzing {school.get('name')} / {major.get('name')}"
        )

        user_content = json.dumps(
            {
                "院校信息": {
                    "名称": school.get("name"),
                    "省份": school.get("province"),
                    "层次": school.get("level"),
                    "类型": school.get("school_type"),
                    "简介": (school.get("description") or "")[:150],
                },
                "专业信息": {
                    "名称": major.get("name"),
                    "代码": major.get("code"),
                    "学位类型": major.get("degree_level", ""),
                    "考试科目": major.get("exam_subjects", ""),
                },
                "预估分数": estimated_score or "未提供",
                "历年分数线": score_lines[-10:] if score_lines else [],
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content + "\n\n请基于以上数据给出该院校+专业的择校分析。"},
                ],
                temperature=0.4,
                max_tokens=2000,
            )

            content = resp.choices[0].message.content or "{}"
            return self._parse_analyze_response(content)

        except Exception as e:
            logger.error(f"Orchestrator single analysis failed: {e}")
            return AnalyzeResult(
                risk_level="未知",
                match_score=0,
                score_trend="",
                competition="",
                pros=[],
                cons=[],
                analysis="分析服务暂时不可用，请稍后重试",
                preparation_tips="",
                raw_text="",
            )

    def _parse_analyze_response(self, content: str) -> AnalyzeResult:
        data = _extract_json(content)
        if data is None:
            return AnalyzeResult(
                risk_level="未知", match_score=0, score_trend="",
                competition="", pros=[], cons=[],
                analysis=content[:500], preparation_tips="", raw_text=content,
            )

        return AnalyzeResult(
            risk_level=data.get("risk_level", "未知"),
            match_score=float(data.get("match_score", 0)),
            score_trend=data.get("score_trend", ""),
            competition=data.get("competition", ""),
            pros=data.get("pros", []),
            cons=data.get("cons", []),
            analysis=data.get("analysis", ""),
            preparation_tips=data.get("preparation_tips", ""),
            raw_text=content,
        )


orchestrator = OrchestratorAgent()


def _extract_json(content: str) -> dict | None:
    """Extract the first valid JSON object from LLM response text.

    Returns the parsed dict, or None if nothing parses.
    """
    if not content:
        return None
    content = content.strip()
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    last_open = content.rfind('{')
    if last_open >= 0:
        try:
            return json.loads(content[last_open:])
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None
