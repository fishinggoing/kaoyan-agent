"""
NeedsAnalysisAgent — conversational needs assessment via DeepSeek.

This agent engages the user in natural-language dialogue to understand:
- Career goals and motivation for graduate study
- Geographic preferences and constraints
- School tier vs. major quality trade-off priorities
- Risk tolerance (play safe vs. reach high)
- Subject strengths and weaknesses in context

After the conversation, it extracts structured preference_weights JSON
that feeds directly into the recommendation scoring algorithm.
"""

import json
import re
import logging
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的考研择校顾问，正在通过对话了解一位考生的真实需求和偏好。

你的任务：
1. 通过友好对话了解考生的：职业目标、地域偏好、学校层次偏好、专业偏好、风险承受度、学科强项与弱项
2. 根据考生的回答，提出有针对性的追问（每次只问1-2个最重要的问题）
3. 不要重复已经问过的问题
4. 如果你认为可以了，就给用户输出推荐的学校

对话策略：
- 先了解大局（为什么考研？想去哪里？），再深入细节
- 如果考生回答模糊，用具体选项引导（"你更看重学校层次还是专业对口？"）
- 注意考生的情绪和语气，调整建议风格
- 【重要】当考生询问学校推荐、择校建议，或已明确基本需求后，你应主动在回复中列出2-5所具体学校（官方全称如"暨南大学""华东师范大学"）。系统会自动识别学校名并生成信息卡片。不需要等考生说"推荐"关键词

当信息足够或用户表示完成时，在回复末尾附加权重JSON块：
```weights
{
  "province_priority": 0.0-1.0,
  "level_priority": 0.0-1.0,
  "major_priority": 0.0-1.0,
  "score_priority": 0.0-1.0,
  "major_strength_priority": 0.0-1.0,
  "risk_tolerance": "保守" | "适中" | "激进",
  "career_goal": "学术界" | "工业界" | "公务员" | "创业" | "未定",
  "preferred_cities": ["城市名"],
  "preferred_majors": ["专业方向"],
  "excluded_provinces": [],
  "reasoning": "基于对话总结的用户需求，50字以内"
}
```

权重含义：
- province_priority: 地域重要性，越高越倾向特定省份/城市
- level_priority: 学校层次(985/211等)重要性
- major_priority: 专业匹配度重要性
- score_priority: 分数安全性重要性，越高越倾向分数匹配的稳妥选择
- major_strength_priority: 学科实力重要性，越高越看重学校在目标专业领域的学科评估排名
- risk_tolerance: 保守=多保底、激进=多冲刺

注意：
- 权重是相对的，不是所有都为1.0；总和不应全部偏高
- 如果用户确实没提到某方面，给0.5（中性）
- 对话正常进行，不要每轮都输出权重；只在信息充分或用户要求时才输出
- 输出权重前先自然总结你的理解，然后附加权重块"""


@dataclass
class NeedsAnalysisResult:
    reply: str
    weights: dict | None = None
    is_complete: bool = False
    intents: list[str] = None  # ["recommend", "plan"]
    intent_params: dict | None = None  # {recommend: {province, level, major}, plan: {school, major}}
    recommendation_preview: dict | None = None  # inline rec cards from school-name search
    school_names: list[str] = None  # school names extracted from [[SCHOOLS]] markers

    def __post_init__(self):
        if self.intents is None:
            self.intents = []
        if self.intent_params is None:
            self.intent_params = {}
        if self.school_names is None:
            self.school_names = []


class NeedsAnalysisAgent:
    """Conversational agent that extracts weighted user preferences."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model

    def _build_profile_context(self, profile: dict | None) -> str:
        """Build a concise profile summary for injection into the system prompt."""
        if not profile:
            return ""

        parts: list[str] = []
        if profile.get("undergraduate_school"):
            parts.append(f"本科院校：{profile['undergraduate_school']}")
        if profile.get("undergraduate_major"):
            parts.append(f"本科专业：{profile['undergraduate_major']}")
        if profile.get("target_province"):
            parts.append(f"目标省份：{profile['target_province']}")
        if profile.get("target_level"):
            parts.append(f"目标层次：{profile['target_level']}")
        if profile.get("estimated_score"):
            parts.append(f"预估分数：{profile['estimated_score']}分")
        if profile.get("exam_year"):
            parts.append(f"考研年份：{profile['exam_year']}年")

        exam = profile.get("exam_config") or {}
        exam_parts = []
        if exam.get("math"):
            exam_parts.append(exam["math"])
        if exam.get("english"):
            exam_parts.append(exam["english"])
        if exam_parts:
            parts.append(f"考试科目：{'、'.join(exam_parts)}")

        strengths = profile.get("subject_strengths") or {}
        if strengths:
            strength_parts = []
            for k, v in strengths.items():
                label = "优势" if v == "强" else ("薄弱" if v == "弱" else "一般")
                strength_parts.append(f"{k}（{label}）")
            if strength_parts:
                parts.append(f"学科强弱：{'、'.join(strength_parts)}")

        if not parts:
            return ""

        return "考生已填写的个人资料（可能不准确，需要先向考生确认）：\n" + "\n".join(f"- {p}" for p in parts)

    def _build_system_prompt(self, profile: dict | None, history: list[dict]) -> str:
        """Build the system prompt with optional profile context."""
        profile_context = self._build_profile_context(profile)

        if not profile_context:
            return SYSTEM_PROMPT

        is_first_message = len([m for m in history if m.get("role") == "user"]) == 0

        if is_first_message:
            return SYSTEM_PROMPT + f"""

【重要】以下是考生在系统中填写的个人资料：
{profile_context}

这是考生的第一条消息。你需要：
1. 先总结你了解到的考生信息
2. 请考生确认这些信息是否准确——"这些信息对吗？有哪些需要更正的吗？"
3. 考生确认后，再针对资料中缺失的信息追问（如职业目标、具体城市偏好、风险承受度等）
4. 不要在考生确认前就基于这些资料做推荐"""
        else:
            return SYSTEM_PROMPT + f"""

【考生资料参考】：
{profile_context}

注意：以上资料考生可能已确认或更正。请根据对话中的确认情况使用这些信息。
- 如果考生在对话中更正了某项，以对话为准
- 如果考生确认了这些信息，可以直接使用，不再重复询问"""

    async def chat(
        self, history: list[dict], user_message: str, profile: dict | None = None
    ) -> NeedsAnalysisResult:
        """Process a user message and return the agent's reply.

        Args:
            history: Previous messages in format [{"role": "user"|"assistant", "content": "..."}]
            user_message: The current user message
            profile: Optional profile dict with fields like undergraduate_school,
                     estimated_score, target_province, exam_config, subject_strengths, etc.

        Returns:
            NeedsAnalysisResult with the agent's reply and optionally extracted weights
        """
        system_content = self._build_system_prompt(profile, history)

        messages = [
            {"role": "system", "content": system_content},
        ]

        # Build conversation history (last 10 rounds to keep context manageable)
        for msg in history[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.5,
                max_tokens=800,
            )

            content = resp.choices[0].message.content or ""

            # Extract school markers from LLM response
            content, school_names = self._extract_school_markers(content)

            # Check for weights block in the response
            weights = self._extract_weights(content)
            is_complete = weights is not None

            # If complete, strip the weights block from the visible reply
            clean_reply = content
            if weights:
                clean_reply = re.sub(r"```weights[\s\S]*?```", "", content).strip()

            intents = self._detect_intents(user_message)
            intent_params = self._extract_intent_params(history, user_message, intents) if intents else {}

            return NeedsAnalysisResult(
                reply=clean_reply or content,
                weights=weights,
                is_complete=is_complete,
                intents=intents,
                intent_params=intent_params,
                school_names=school_names,
            )

        except Exception as e:
            logger.error(f"NeedsAnalysisAgent.chat failed: {e}")
            return NeedsAnalysisResult(
                reply="抱歉，我暂时无法分析你的需求。请稍后重试。",
                weights=None,
                is_complete=False,
            )

    async def finalize(self, history: list[dict]) -> NeedsAnalysisResult:
        """Force extraction of weights from the full conversation history.

        This is called when the user clicks "完成分析" even if the agent
        hasn't naturally reached a conclusion.
        """
        conversation_text = "\n".join(
            f"{'考生' if m.get('role') == 'user' else '顾问'}: {m.get('content', '')}"
            for m in history[-20:]
        )

        prompt = f"""以下是和一位考研考生的对话：

{conversation_text}

请根据以上对话，严格按以下格式输出该考生的偏好权重JSON（用```weights包裹）：

{{
  "province_priority": 0.0-1.0,
  "level_priority": 0.0-1.0,
  "major_priority": 0.0-1.0,
  "score_priority": 0.0-1.0,
  "risk_tolerance": "保守" | "适中" | "激进",
  "career_goal": "学术界" | "工业界" | "公务员" | "创业" | "未定",
  "preferred_cities": ["城市名"],
  "preferred_majors": ["专业方向"],
  "excluded_provinces": [],
  "reasoning": "基于对话总结的用户需求，50字以内"
}}

字段含义：
- province_priority: 地域重要性（用户强调特定城市/省份→0.8+；无所谓→0.3-0.5）
- level_priority: 学校层次重要性（看重985/211→0.8+；无所谓→0.3-0.5）
- major_priority: 专业匹配重要性（专业必须对口→0.9+；可接受跨专业→0.3-0.5）
- score_priority: 分数安全性（求稳→0.8+；可冲刺→0.3-0.5）
- risk_tolerance: "激进"=多冲刺、"保守"=多保底、"适中"=平衡
- career_goal: 从对话推断的职业目标
- preferred_cities: 用户提到的偏好城市列表
- preferred_majors: 用户提到的偏好专业方向
- excluded_provinces: 用户明确排除的省份
- reasoning: 一句话总结用户需求

必须输出```weights包裹的JSON，不要省略任何字段。"""

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位考研择校顾问。根据对话历史提取用户偏好权重。只输出权重JSON，不要其他内容。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = resp.choices[0].message.content or ""

            # Extract school markers
            content, school_names = self._extract_school_markers(content)

            weights = self._extract_weights(content)

            # Get last user message for intent detection
            last_user = ""
            for m in reversed(history):
                if m.get("role") == "user":
                    last_user = m.get("content", "")
                    break
            intents = self._detect_intents(last_user)
            intent_params = self._extract_intent_params(history, last_user, intents) if intents else {}

            if weights:
                return NeedsAnalysisResult(
                    reply="已根据对话内容分析完成，请查看你的偏好权重设置。",
                    weights=weights,
                    is_complete=True,
                    intents=intents,
                    intent_params=intent_params,
                    school_names=school_names,
                )

            return NeedsAnalysisResult(
                reply="抱歉，无法从对话中提取足够信息。请再多告诉我一些关于你的情况。",
                weights=None,
                is_complete=False,
                intents=intents,
                intent_params=intent_params,
                school_names=school_names,
            )

        except Exception as e:
            logger.error(f"NeedsAnalysisAgent.finalize failed: {e}")
            return NeedsAnalysisResult(
                reply="分析过程出现错误，请稍后重试。",
                weights=None,
                is_complete=False,
            )

    RECOMMEND_KEYWORDS = [
        "推荐学校", "择校", "帮我推荐", "帮我选", "选学校", "有什么推荐",
        "建议报", "适合我", "能报", "可以报", "院校推荐", "推荐一下",
        "推荐院校", "学校推荐", "有什么学校", "给我推荐", "推荐几所",
        "有哪些学校", "哪些学校", "帮我看看", "给我点建议", "有什么选择",
        "推荐几个", "什么学校好",
    ]
    PROVINCES = [
        "北京", "上海", "广东", "江苏", "浙江", "湖北", "湖南", "四川",
        "陕西", "山东", "天津", "重庆", "辽宁", "吉林", "黑龙江",
        "福建", "安徽", "江西", "河南", "河北", "山西", "甘肃", "云南", "贵州",
        "广西", "海南", "内蒙古", "宁夏", "青海", "西藏", "新疆",
    ]
    LEVELS = ["C9", "985", "211", "军事院校", "中外合作", "双一流", "普本"]
    LEVEL_ALIASES = {
        "九八五": "985", "二一一": "211", "二幺幺": "211",
        "双一流": "双一流", "省重点": "普本", "一本": "普本", "二本": "普本",
        "军校": "军事院校", "军事": "军事院校",
        "中外合作": "中外合作", "合作办学": "中外合作",
    }
    MAJOR_KEYWORDS = [
        "计算机", "软件工程", "人工智能", "数据科学", "金融", "会计",
        "法学", "医学", "临床医学", "机械", "土木", "电气", "电子",
        "通信", "材料", "化工", "化学", "物理", "数学", "生物",
        "经济学", "管理学", "工商管理", "MBA", "新闻", "传播",
        "外语", "英语", "日语", "历史", "哲学", "教育学", "心理学",
        "社会学", "政治学", "公共管理", "环境", "建筑", "城乡规划",
        "设计", "艺术", "体育", "自动化", "仪器", "能源", "动力",
        "集成电路", "芯片", "半导体", "光学", "网络安全", "信息安全",
    ]

    SCHOOL_MARKER = re.compile(r'\[\[SCHOOLS\]\]\s*([\s\S]*?)\[\[/SCHOOLS\]\]')
    # Fallback regex: match school names like "XX大学" or "XX学院" (2-8 Chinese chars prefix)
    SCHOOL_NAME_RE = re.compile(r'([一-鿿]{2,8}(?:大学|学院))')

    def _extract_school_markers(self, text: str) -> tuple[str, list[str]]:
        """Extract school names from LLM response.

        Primary: [[SCHOOLS]]...[[/SCHOOLS]] markers.
        Fallback: regex scan for any school names (XX大学/XX学院) in the text.
        """
        schools: list[str] = []
        clean_text = text

        # Primary: explicit markers
        marker_found = False
        for match in self.SCHOOL_MARKER.finditer(text):
            marker_found = True
            for line in match.group(1).strip().split('\n'):
                name = line.strip()
                if name and len(name) >= 4:
                    schools.append(name)

        if marker_found:
            clean_text = self.SCHOOL_MARKER.sub('', text).strip()
            return clean_text, schools

        # Fallback: scan entire LLM response for school names
        seen: set[str] = set()
        for m in self.SCHOOL_NAME_RE.finditer(text):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                schools.append(name)

        return clean_text, schools[:10]

    def _detect_intents(self, user_message: str, assistant_reply: str = "") -> list[str]:
        """Detect user intent from the combined text of the current turn."""
        combined = f"{user_message} {assistant_reply}"
        intents = []
        if any(kw in combined for kw in self.RECOMMEND_KEYWORDS):
            intents.append("recommend")
        return intents

    def _extract_intent_params(
        self, history: list[dict], user_message: str, intents: list[str]
    ) -> dict:
        """Extract structured parameters from conversation for intent chips.

        Uses regex to find provinces, school levels, major keywords, and school
        names mentioned in the recent conversation and current user message.
        No additional LLM call — fast and deterministic.
        """
        # Build combined text from last few rounds + current message
        parts = [user_message]
        for m in history[-6:]:
            parts.append(m.get("content", ""))
        combined = " ".join(parts)

        params: dict = {}

        if "recommend" in intents:
            rec: dict = {}
            # Provinces
            found_provinces = [p for p in self.PROVINCES if p in combined]
            if found_provinces:
                rec["target_province"] = found_provinces[0]
                rec["provinces_mentioned"] = found_provinces[:5]

            # Levels
            for alias, canonical in self.LEVEL_ALIASES.items():
                if alias in combined:
                    rec["target_level"] = canonical
                    break
            if "target_level" not in rec:
                for level in self.LEVELS:
                    if level in combined:
                        rec["target_level"] = level
                        break

            # Major keywords
            found_majors = [m for m in self.MAJOR_KEYWORDS if m in combined]
            if found_majors:
                rec["major_keyword"] = found_majors[0]

            # School names: match 2-4 Chinese chars + 大学/学院 suffix
            school_pattern = re.compile(r"([一-鿿]{2,4}(?:大学|学院))")
            found_schools = list(dict.fromkeys(school_pattern.findall(combined)))
            if found_schools:
                rec["schools_mentioned"] = found_schools[:5]

            if rec:
                params["recommend"] = rec

        return params

    def _extract_weights(self, text: str) -> dict | None:
        """Extract weights JSON from agent response text and normalize to expected schema."""
        candidate = None

        # Try ```weights ... ``` block first
        match = re.search(r"```weights\s*([\s\S]*?)```", text)
        if match:
            try:
                candidate = json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback: try to find any JSON object with priority/risk keys
        if candidate is None:
            for m in re.finditer(r"\{[\s\S]*?\}", text):
                try:
                    obj = json.loads(m.group())
                    if any(k in obj for k in (
                        "province_priority", "level_priority", "major_priority",
                        "risk_tolerance", "location", "major_relevance",
                    )):
                        candidate = obj
                        break
                except json.JSONDecodeError:
                    continue

        if candidate is None:
            return None

        return self._normalize_weights(candidate)

    def _normalize_weights(self, raw: dict) -> dict:
        """Normalize raw LLM output to the standard preference_weights schema."""
        def clamp(v):
            try:
                return round(max(0.0, min(1.0, float(v or 0.5))), 1)
            except (ValueError, TypeError):
                return 0.5

        risk_raw = str(raw.get("risk_tolerance", "")).strip()
        risk = "适中"
        if "激进" in risk_raw or "冲刺" in risk_raw:
            risk = "激进"
        elif "保守" in risk_raw or "保底" in risk_raw:
            risk = "保守"

        return {
            "province_priority": clamp(raw.get("province_priority", raw.get("location", 0.5))),
            "level_priority": clamp(raw.get("level_priority", raw.get("school_ranking", 0.5))),
            "major_priority": clamp(raw.get("major_priority", raw.get("major_relevance", 0.5))),
            "score_priority": clamp(raw.get("score_priority", raw.get("employment_prospect", 0.5))),
            "major_strength_priority": clamp(raw.get("major_strength_priority", 0.3)),
            "risk_tolerance": risk,
            "career_goal": str(raw.get("career_goal", "未定")),
            "preferred_cities": raw.get("preferred_cities", []) or [],
            "preferred_majors": raw.get("preferred_majors", []) or [],
            "excluded_provinces": raw.get("excluded_provinces", []) or [],
            "reasoning": str(raw.get("reasoning", ""))[:80],
        }


# Singleton
needs_analysis_agent = NeedsAnalysisAgent()
