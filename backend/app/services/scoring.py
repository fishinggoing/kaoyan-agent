"""
Scoring utilities for the decision recommendation pipeline.

Extracted from decision_service.py to keep files under the 800-line limit.
Pure-Python computation functions: keyword matching, weighted scoring,
profile building, and lookup construction.
"""

import json
import math
import re

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models import School, Major, SchoolMajor, UserProfile
from app.agents.orchestrator import RecommendationItem
from app.data.school_admissions import get_dual_non_penalty, get_admissions_summary

# Estimated re-exam cutoff premium by school tier (复试线估算溢价).
# Applied when real re_exam_total_score data is unavailable.
TIER_RE_EXAM_PREMIUM: dict[str, int] = {
    "C9": 25, "985": 15, "211": 8, "军事院校": 8, "中外合作": 8, "双一流": 5, "普本": 0,
}

# School tier difficulty multiplier (学校层级难度乘数).
# Reflects non-score admission barriers: re-exam elimination rate,
# interview rigor, undergraduate prestige bias, research expectations.
TIER_DIFFICULTY_MULTIPLIER: dict[str, float] = {
    "C9": 1.20, "985": 1.10, "211": 1.05, "军事院校": 1.05, "中外合作": 1.05, "双一流": 1.02, "普本": 1.00,
}

# Tier ordering for background gap penalty (undergrad → target school).
# Each tier gap costs ~7 points on school_match, making ambitious jumps harder.
TIER_ORDER: dict[str, int] = {
    "普本": 0, "双一流": 1, "211": 2, "军事院校": 2, "中外合作": 2, "985": 3, "C9": 4,
}


def _tier_gap_penalty(background_tier: str, target_tier: str) -> int:
    """Penalty when target school tier exceeds undergraduate background tier."""
    if not background_tier or not target_tier:
        return 0
    bg = TIER_ORDER.get(background_tier, 0)
    tg = TIER_ORDER.get(target_tier, 0)
    gap = tg - bg
    if gap <= 0:
        return 0
    return gap * 5


def _score_component(estimated: int, effective_cutoff: float) -> int:
    """Score-fit component using tanh for diminishing returns. Range 25–75.

    A student 30+ points above the cutoff gets near-max score (74+);
    further surplus adds little. Being 30+ below bottoms out at ~25.
    """
    if estimated <= 0 or effective_cutoff <= 0:
        return 50
    diff = estimated - effective_cutoff
    return round(50 + 25 * math.tanh(diff / 30))


def _background_risk_shift(background_tier: str, target_tier: str) -> int:
    """Tighten risk threshold when undergrad tier is below target tier.

    A 双非 student targeting 985 needs a higher score surplus for the same
    risk classification because of implicit interview bias and fewer connections.
    """
    if not background_tier or not target_tier:
        return 0
    return BACKGROUND_RISK_SHIFT.get((background_tier, target_tier), 0)


def _first_choice_bonus_from_admissions(school_name: str, school_level: str) -> int:
    """Look up first-choice protection bonus from school admissions data."""
    from app.data.school_admissions import lookup as adm_lookup
    data = adm_lookup(school_name, school_level)
    pfc = data.get("protect_first_choice")
    if pfc is True:
        return FIRST_CHOICE_BONUS["protect"]
    elif pfc is False:
        return FIRST_CHOICE_BONUS["no_protect"]
    return 0

# Research institutes: low 初试 bar but strict 复试 elimination.
# Use near-neutral tier multiplier since 初试 scores aren't the real barrier.
INSTITUTE_TIER_MULTIPLIER = 1.02

# 教育部第四轮学科评估 rating → numeric score (0-100).
# Schools without a rating get 50 (neutral) — only strong programs get a boost.
RATING_TO_SCORE: dict[str, int] = {
    "A+": 100, "A": 92, "A-": 85,
    "B+": 78, "B": 70, "B-": 62,
    "C+": 55, "C": 50, "C-": 42,
}

# Reverse lookup: numeric rating score → letter grade label
_SCORE_TO_RATING: dict[int, str] = {v: k for k, v in RATING_TO_SCORE.items()}

# Program-strength difficulty bonus: top-rated programs have higher effective cutoffs.
# A 211 school with an A-rated CS program can be harder to enter than a 985 with C-rated CS.
MAJOR_DIFFICULTY_BONUS: dict[str, float] = {
    "A+": 0.10, "A": 0.06, "A-": 0.04,
    "B+": 0.02, "B": 0.00, "B-": -0.02,
    "C+": -0.03, "C": -0.05, "C-": -0.08,
}

# Bonus/penalty for first-choice protection policy.
FIRST_CHOICE_BONUS: dict[str, int] = {
    "protect": 8,
    "no_protect": -5,
}

# Background-aware risk shift: when undergrad tier is below target tier,
# the risk threshold tightens (more conservative).
BACKGROUND_RISK_SHIFT: dict[tuple[str, str], int] = {
    ("普本", "C9"): -15, ("普本", "985"): -10, ("普本", "211"): -5,
    ("双一流", "C9"): -10, ("双一流", "985"): -5,
}

# Patterns that identify a school as a research institute rather than a university.
_RESEARCH_INSTITUTE_PATTERNS = [
    "中国科学院", "中国社会科学院", "研究院", "中国工程物理研究院",
]


def is_research_institute(school_name: str) -> bool:
    """Detect research institutes (研究院/所) by name pattern."""
    return any(p in school_name for p in _RESEARCH_INSTITUTE_PATTERNS)

# Score normalization adjustments for exam subject difficulty (科目难度归一化).
# Normalizes user's estimated score to 数一+英一 baseline.
# Negative = user's subject is easier (scores inflated, deflate to baseline).
# Positive = user's subject is harder (scores deflated, inflate to baseline).
MATH_ADJUST: dict[str, int] = {"数二": -22, "数三": -15, "不考数学": -28, "无数学": -28}
ENGLISH_ADJUST: dict[str, int] = {"英二": -8}
PROF_ADJUST: dict[str, int] = {"408": 5}  # 408 is harder than avg self-designed

# Subject compatibility penalties applied to match_score.
MATH_MISMATCH_PENALTY = 15
ENGLISH_MISMATCH_PENALTY = 8
PROF_MISMATCH_PENALTY = 10

# Direct 学硕 ↔ 专硕 degree equivalents (bidirectional).
# When a user searches for either, BOTH get the same primary (score=100) treatment.
# Based on 国务院学位委员会 学术学位与专业学位对应目录.
DEGREE_EQUIVALENTS: dict[str, str] = {
    # 工学门类 (08)
    "0851": "0813",  # 建筑(专) ↔ 建筑学(学)
    "0854": "0812",  # 电子信息(专) ↔ 计算机/信息/控制/电子(学) — primary anchor
    "0855": "0802",  # 机械(专) ↔ 机械工程(学)
    "0856": "0817",  # 材料与化工(专) ↔ 化学工程(学)
    "0857": "0830",  # 资源与环境(专) ↔ 环境科学与工程(学)
    "0858": "0808",  # 能源动力(专) ↔ 电气工程(学)
    "0859": "0814",  # 土木水利(专) ↔ 土木工程(学)
    "0860": "0836",  # 生物与医药(专) ↔ 生物工程(学)
    "0861": "0823",  # 交通运输(专) ↔ 交通运输工程(学)
    "0862": "0823",  # 风景园林(专) — adjacent to 交通运输/建筑
    # 经济学
    "0251": "0202",  # 金融(专) ↔ 应用经济学(学)
    "0252": "0202",  # 应用统计(专) ↔ 应用经济学(学)
    "0253": "0202",  # 税务(专) ↔ 应用经济学(学)
    "0254": "0202",  # 国际商务(专) ↔ 应用经济学(学)
    "0255": "0202",  # 保险(专) ↔ 应用经济学(学)
    "0256": "0202",  # 资产评估(专) ↔ 应用经济学(学)
    # 法学
    "0351": "0301",  # 法律(专) ↔ 法学(学)
    "0352": "0302",  # 社会工作(专) ↔ 政治学(学)
    # 教育学
    "0451": "0401",  # 教育(专) ↔ 教育学(学)
    "0452": "0403",  # 体育(专) ↔ 体育学(学)
    "0453": "0501",  # 汉语国际教育(专) ↔ 中国语言文学(学)
    "0454": "0402",  # 应用心理(专) ↔ 心理学(学)
    # 文学/翻译
    "0551": "0502",  # 翻译(专) ↔ 外国语言文学(学)
    "0552": "0503",  # 新闻与传播(专) ↔ 新闻传播学(学)
    "0553": "0503",  # 出版(专) ↔ 新闻传播学(学)
    # 历史学
    "0651": "0601",  # 文物与博物馆(专) ↔ 考古学(学)
    # 农学
    "0951": "0901",  # 农业(专) ↔ 作物学(学)
    "0952": "0902",  # 兽医(专) ↔ 兽医学(学)
    "0953": "0905",  # 风景园林(专) ↔ 林学(学)
    "0954": "0907",  # 林业(专) ↔ 林学(学)
    # 医学
    "1051": "1002",  # 临床医学(专) ↔ 临床医学(学)
    "1052": "1002",  # 口腔医学(专) ↔ 口腔医学(学)
    "1053": "1004",  # 公共卫生(专) ↔ 公共卫生(学)
    "1054": "1002",  # 护理(专) ↔ 护理学(学)
    "1055": "1007",  # 药学(专) ↔ 药学(学)
    "1056": "1008",  # 中药学(专) ↔ 中药学(学)
    "1057": "1006",  # 中医(专) ↔ 中西医结合(学)
    # 管理学
    "1251": "1201",  # 工商管理(专) ↔ 管理科学与工程(学)
    "1252": "1204",  # 公共管理(专) ↔ 公共管理(学)
    "1253": "1202",  # 会计(专) ↔ 工商管理(学)
    "1254": "1203",  # 旅游管理(专) ↔ 农林经济管理(学)
    "1255": "1205",  # 图书情报(专) ↔ 图书馆/情报/档案管理(学)
    "1256": "1202",  # 工程管理(专) ↔ 工商管理(学)
    # 艺术学
    "1351": "1301",  # 艺术(专) ↔ 艺术学理论(学)
    "1352": "1301",  # 音乐(专) ↔ 艺术学理论(学)
    "1353": "1301",  # 舞蹈(专) ↔ 艺术学理论(学)
    "1354": "1301",  # 戏剧与影视(专) ↔ 艺术学理论(学)
    "1355": "1301",  # 美术与书法(专) ↔ 艺术学理论(学)
    "1356": "1301",  # 设计(专) ↔ 艺术学理论(学)
}
# Build reverse mapping: 学硕 → 专硕
_DEGREE_EQUIV_REVERSE: dict[str, list[str]] = {}
for _k, _v in DEGREE_EQUIVALENTS.items():
    _DEGREE_EQUIV_REVERSE.setdefault(_v, []).append(_k)

# 6-digit 专硕方向 → 4-digit 学硕 prefix — finer than DEGREE_EQUIVALENTS.
# When a user's keyword matches a specific 6-digit 专硕 sub-direction, the
# matching 学硕 is promoted to primary (score=100).  This solves the "085403
# 集成电路工程 ↔ 140100 集成电路科学与工程" granularity problem.
SUBDEGREE_EQUIVALENTS: dict[str, str] = {
    # ── 0854 电子信息 (12 sub-directions) ──
    "085401": "0812",  # 计算机技术 → 计算机科学与技术(学)
    "085402": "0810",  # 通信工程 → 信息与通信工程(学)
    "085403": "1401",  # 集成电路工程 → 集成电路科学与工程(交叉,1401)
    "085404": "0811",  # 控制工程 → 控制科学与工程(学)
    "085405": "0804",  # 仪器仪表工程 → 仪器科学与技术(学)
    "085406": "0803",  # 光电信息工程 → 光学工程(学)
    "085407": "0812",  # 人工智能 → 计算机/智能科学(学)
    "085408": "0812",  # 大数据技术与工程 → 计算机(学)
    "085409": "0839",  # 网络与信息安全 → 网络空间安全(学)
    "085410": "0809",  # 新一代电子信息技术 → 电子科学与技术(学)
    "085411": "0831",  # 生物医学工程(专) → 生物医学工程(学)
    "085412": "0835",  # 软件工程(专) → 软件工程(学)
    # ── 0855 机械 ──
    "085501": "0802",  # 机械工程
    "085502": "0802",  # 车辆工程
    "085503": "0802",  # 航空工程
    "085504": "0802",  # 航天工程
    "085505": "0802",  # 智能制造技术
    "085506": "0802",  # 工业设计工程
    "085507": "0825",  # 兵器工程 → 兵器科学与技术
    # ── 0856 材料与化工 ──
    "085601": "0805",  # 材料工程 → 材料科学与工程(学)
    "085602": "0817",  # 化学工程 → 化学工程与技术(学)
    "085603": "0821",  # 纺织工程 → 纺织科学与工程(学)
    "085604": "0817",  # 轻化工程
    "085605": "0822",  # 轻工技术与工程
    "085606": "0805",  # 材料工程(高分子方向)
    # ── 0857 资源与环境 ──
    "085701": "0830",  # 环境工程
    "085702": "0816",  # 测绘工程 → 测绘科学与技术
    "085703": "0818",  # 地质工程 → 地质资源与地质工程
    "085704": "0819",  # 矿业工程 → 矿业工程
    "085705": "0825",  # 航空宇航 → 航空宇航科学与技术
    "085706": "0837",  # 安全工程 → 安全科学与工程
    # ── 0858 能源动力 ──
    "085801": "0807",  # 动力工程 → 动力工程及工程热物理(学)
    "085802": "0808",  # 电气工程 → 电气工程(学)
    "085803": "0807",  # 清洁能源技术
    "085804": "0807",  # 储能技术
    # ── 0859 土木水利 ──
    "085901": "0814",  # 土木工程
    "085902": "0815",  # 水利工程 → 水利工程(学)
    "085903": "0814",  # 市政工程
    "085904": "0813",  # 建筑环境与能源应用
    # ── 0860 生物与医药 ──
    "086001": "0836",  # 生物工程 → 生物工程(学)
    "086002": "0831",  # 制药工程 → 生物医学工程/药学
    "086003": "0832",  # 食品工程 → 食品科学与工程(学)
    # ── 0861 交通运输 ──
    "086101": "0823",  # 交通运输工程
    "086102": "0823",  # 交通规划与管理
    "086103": "0823",  # 载运工具运用工程
    # ── 其他门类 ──
    "095131": "0904",  # 植物保护(专) → 植物保护(学)
    "095132": "0901",  # 作物学(专) → 作物学(学)
    "095133": "0906",  # 畜牧(专) → 畜牧学(学)
    "095134": "0902",  # 兽医(专) → 兽医学(学)
    "095135": "0907",  # 林业(专) → 林学(学)
    "095136": "0908",  # 水产(专) → 水产(学)
    "095137": "0903",  # 农业资源利用 → 农业资源与环境(学)
    # ── 医学 ──
    "105101": "1002",  # 内科学(专) → 临床医学(学)
    "105102": "1002",  # 外科学(专)
    "105103": "1002",  # 妇产科学(专)
    "105104": "1002",  # 儿科学(专)
    "105105": "1002",  # 眼科学(专)
    "105106": "1002",  # 耳鼻咽喉科学(专)
    "105107": "1002",  # 肿瘤学(专)
    "105108": "1002",  # 康复医学(专)
    "105109": "1002",  # 麻醉学(专)
    "105110": "1002",  # 急诊医学(专)
    "105111": "1002",  # 全科医学(专)
    "105112": "1002",  # 临床病理(专)
    "105113": "1002",  # 影像医学与核医学(专)
    "105114": "1002",  # 临床检验诊断学(专)
    # ── 0451 教育硕士 — 学科教学方向映射到不同学科 ──
    "045102": "0305",  # 学科教学(思政) → 马克思主义理论(学)
    "045103": "0501",  # 学科教学(语文) → 中国语言文学(学)
    "045104": "0701",  # 学科教学(数学) → 数学(学)
    "045105": "0702",  # 学科教学(物理) → 物理学(学)
    "045106": "0703",  # 学科教学(化学) → 化学(学)
    "045107": "0710",  # 学科教学(生物) → 生物学(学)
    "045108": "0502",  # 学科教学(英语) → 外国语言文学(学)
    "045109": "0602",  # 学科教学(历史) → 中国史(学)
    "045110": "0705",  # 学科教学(地理) → 地理学(学)
    "045111": "1301",  # 学科教学(音乐) → 艺术学(学)
    "045112": "0403",  # 学科教学(体育) → 体育学(学)
    "045113": "1301",  # 学科教学(美术) → 艺术学(学)
    "045114": "0401",  # 现代教育技术 → 教育学(学)
    "045115": "0401",  # 小学教育 → 教育学(学)
    "045116": "0402",  # 心理健康教育 → 心理学(学)
    "045117": "0401",  # 科学与技术教育 → 教育学(学)
    "045118": "0401",  # 学前教育 → 教育学(学)
    "045119": "0401",  # 特殊教育 → 教育学(学)
    "045120": "0401",  # 职业技术教育 → 教育学(学)
    # ── 0851 建筑学 ──
    "085101": "0813",  # 建筑设计及其理论
    "085102": "0833",  # 城市规划与设计 → 城乡规划学(学)
    "085103": "0813",  # 建筑技术科学
    "085104": "0813",  # 建筑历史与理论
    # ── 1251 工商管理 MBA sub-directions ──
    "125101": "1201",  # 工商管理 → 管理科学与工程(学)
    "125102": "1202",  # 高级工商管理(EMBA) → 工商管理(学)
    # ── 1252 公共管理 MPA ──
    "125201": "1204",  # 公共管理 → 公共管理(学)
    "125202": "1204",  # 公共政策 → 公共管理(学)
    # ── 1253 会计 ──
    "125301": "1202",  # 会计 → 工商管理(学)
    "125302": "1202",  # 审计 → 工商管理(学)
    # ── 1351 艺术 sub-directions (部分方向对应不同学硕) ──
    "135101": "1301",  # 音乐
    "135102": "1301",  # 戏剧
    "135103": "1301",  # 戏曲
    "135104": "1301",  # 电影
    "135105": "1301",  # 广播电视
    "135106": "1302",  # 舞蹈 → 音乐与舞蹈学(学)
    "135107": "1304",  # 美术 → 美术学(学)
    "135108": "1305",  # 艺术设计 → 设计学(学)
}
# Build 4-digit reverse: given a 学硕 prefix found in SUBDEGREE, find all 专硕 4-digit parents
_SUBDEGREE_REVERSE: dict[str, set[str]] = {}
for _k6, _v4 in SUBDEGREE_EQUIVALENTS.items():
    _k4 = _k6[:4]
    _SUBDEGREE_REVERSE.setdefault(_v4, set()).add(_k4)

# Intra-field adjacency — same broad field but different specific disciplines.
# These are NOT direct equivalents; they get score=70 (related), not 100.
DISCIPLINE_RELATIVES: dict[str, list[str]] = {
    # 电子信息 family: 0854(专硕) ↔ all its 学硕 siblings
    "0854": ["0809", "0810", "0811", "0812", "0835", "1401", "1405"],
    "0809": ["0810", "0854", "0811", "0812"],
    "0810": ["0809", "0854", "0811", "0812"],
    "0811": ["0812", "0854", "0810", "0809"],
    "0812": ["0835", "0854", "0811", "0810", "1405"],
    "0835": ["0812", "0854"],
    # 机械 family
    "0855": ["0802", "0804"],
    "0802": ["0855", "0804"],
    "0804": ["0802", "0855"],
    # 材料与化工
    "0856": ["0805", "0817", "0821"],
    "0805": ["0856", "0817"],
    "0817": ["0856", "0805"],
    # 土木水利
    "0859": ["0814", "0813", "0815", "0824"],
    "0814": ["0859", "0813"],
    "0813": ["0814", "0859"],
    # 能源动力
    "0858": ["0807", "0808"],
    "0807": ["0858", "0808"],
    "0808": ["0858", "0807"],
    # 资源与环境
    "0857": ["0830", "0816", "0818", "0819", "0825", "0837"],
    "0830": ["0857", "0816", "0818"],
    # 交通运输
    "0861": ["0823"],
    "0823": ["0861"],
    # 生物与医药
    "0860": ["0831", "0836", "0832"],
    "0831": ["0860", "0836"],
    "0836": ["0860", "0831"],
    # 经济学 family
    "0251": ["0252", "0253", "0254", "0255", "0256"],
    "0252": ["0251", "0202"],
    # 管理学 family
    "1253": ["1251", "1202"],
    "1202": ["1253", "1251"],
}


def build_code_prefixes(db: Session, keyword: str) -> dict:
    """Find 4-digit code prefixes matching a major keyword, with related disciplines.

    Uses 6-digit sub-degree mapping (SUBDEGREE_EQUIVALENTS) first for
    granular 专硕方向→学硕 equivalences (e.g. 085403→1401), then falls
    back to broad 4-digit DEGREE_EQUIVALENTS. Direct equivalents are
    promoted to primary (score=100).
    """
    if not keyword or not keyword.strip():
        return {}
    kw = keyword.strip()

    rows = db.execute(
        select(Major.code).where(
            or_(
                Major.discipline.ilike(f"%{kw}%"),
                Major.name.ilike(f"%{kw}%"),
            )
        ).limit(500)
    ).scalars().all()

    primary: set[str] = set()
    codes_6digit: set[str] = set()
    for code in rows:
        if code and len(code) >= 6:
            codes_6digit.add(code[:6])
        if code and len(code) >= 4:
            primary.add(code[:4])

    if not primary:
        return {}

    # Step 1: 6-digit sub-degree equivalents → promote to primary
    # e.g. 085403(集成电路工程)→1401(集成电路科学), add 1401 to primary
    equivalents: set[str] = set()
    for c6 in codes_6digit:
        eq = SUBDEGREE_EQUIVALENTS.get(c6)
        if eq and eq not in primary:
            equivalents.add(eq)
    # Reverse: if we matched a 学硕, pull in its specific 专硕 parents
    # e.g. matched 1401 in DB → 0854 is the parent of 085403
    for prefix in list(primary):
        revs = _SUBDEGREE_REVERSE.get(prefix, set())
        for rev in revs:
            if rev not in primary:
                equivalents.add(rev)

    # Step 2: broad 4-digit DEGREE_EQUIVALENTS
    for prefix in list(primary):
        eq = DEGREE_EQUIVALENTS.get(prefix)
        if eq and eq not in primary:
            equivalents.add(eq)
        revs = _DEGREE_EQUIV_REVERSE.get(prefix, [])
        for rev in revs:
            if rev not in primary:
                equivalents.add(rev)

    primary.update(equivalents)

    # Step 3: intra-field adjacencies → related (score=70)
    related: set[str] = set()
    for prefix in list(primary):
        for rel in DISCIPLINE_RELATIVES.get(prefix, []):
            if rel not in primary:
                related.add(rel)

    # Determine the dominant 2-digit field
    fields = {p[:2] for p in primary}
    same_field = max(fields, key=lambda f: sum(1 for p in primary if p.startswith(f))) if fields else ""

    return {"primary": primary, "related": related, "same_field": same_field}


def score_by_code(major_code: str, code_prefixes: dict | None) -> int:
    """Score major_code against user's target discipline code prefixes. Returns 0-100."""
    if not code_prefixes or not major_code:
        return 0

    prefix4 = major_code[:4]
    prefix2 = major_code[:2]

    if prefix4 in code_prefixes.get("primary", set()):
        return 100
    if prefix4 in code_prefixes.get("related", set()):
        return 70
    if prefix2 == code_prefixes.get("same_field", ""):
        return 35

    return 0


def normalize_score(estimated_score: int, exam_config: dict) -> int:
    """Normalize user's estimated score to 数一+英一 baseline.

    A student scoring 350 with 数二+英二 would score ~333 with 数一+英一,
    because 数二 has fewer topics and 英二 is easier. This adjusts the raw
    estimate so comparisons against school cutoffs (typically 数一+英一) are fair.
    """
    if not exam_config or not estimated_score:
        return estimated_score

    math = exam_config.get("math", "")
    english = exam_config.get("english", "")
    prof = exam_config.get("专业课", "")

    adjustment = 0
    adjustment += MATH_ADJUST.get(math, 0)
    adjustment += ENGLISH_ADJUST.get(english, 0)
    if "408" in str(prof):
        adjustment += PROF_ADJUST.get("408", 0)

    return estimated_score + adjustment


def check_subject_compatibility(
    user_exam: dict, school_subjects: list[str] | None,
) -> tuple[int, list[str]]:
    """Check if user's exam subjects match school requirements.

    Returns (penalty, warnings) where penalty is 0 or negative.
    """
    if not user_exam or not school_subjects:
        return 0, []

    penalty = 0
    warnings: list[str] = []

    user_math = user_exam.get("math", "")
    user_english = user_exam.get("english", "")
    user_prof = user_exam.get("专业课", "")

    # Flatten school subjects for matching
    school_text = " ".join(str(s) for s in school_subjects)

    # Math compatibility
    school_math = _extract_math_level(school_subjects)
    if user_math and school_math and user_math != school_math:
        penalty -= MATH_MISMATCH_PENALTY
        warnings.append(f"科目不匹配：你考{user_math}，该校要求{school_math}")

    # English compatibility
    school_english = _extract_english_level(school_subjects)
    if user_english and school_english and user_english != school_english:
        penalty -= ENGLISH_MISMATCH_PENALTY
        warnings.append(f"科目不匹配：你考{user_english}，该校要求{school_english}")

    # Professional course compatibility
    if user_prof and school_text and _prof_mismatch(user_prof, school_subjects):
        penalty -= PROF_MISMATCH_PENALTY
        warnings.append(f"专业课不匹配：你考{user_prof}，该校要求不同")

    return penalty, warnings


def _extract_math_level(subjects: list[str]) -> str:
    for s in subjects:
        s_str = str(s)
        if "数一" in s_str:
            return "数一"
        if "数二" in s_str:
            return "数二"
        if "数三" in s_str:
            return "数三"
        if "数学一" in s_str:
            return "数一"
        if "数学二" in s_str:
            return "数二"
        if "数学三" in s_str:
            return "数三"
    return ""


def _extract_english_level(subjects: list[str]) -> str:
    for s in subjects:
        s_str = str(s)
        if "英一" in s_str or "英语一" in s_str:
            return "英一"
        if "英二" in s_str or "英语二" in s_str:
            return "英二"
    return ""


def _prof_mismatch(user_prof: str, school_subjects: list[str]) -> bool:
    """Detect if user's professional course is fundamentally different."""
    if not user_prof:
        return False
    for s in school_subjects:
        s_str = str(s)
        if user_prof in s_str or s_str in user_prof:
            return False
    # 408 is a specific unified exam — check if that's what school expects
    if "408" in user_prof:
        for s in school_subjects:
            if "408" in str(s):
                return False
        return True  # user has 408 but school doesn't require it
    return False


def score_major_keyword(keyword: str, major_name: str, first_level: str = "",
                       category: str = "", major_code: str = "",
                       code_prefixes: dict | None = None) -> int:
    """Score how well a major matches a user keyword. Returns 0-100.

    When code_prefixes are available, code-based matching takes priority over
    text matching (since discipline codes are authoritative). Text matching
    serves as fallback for keywords that don't map to known codes.

    Tiers:
    - 100: code prefix match (primary) or exact name match
    - 90:  split-part fuzzy name match
    - 85:  substring name match
    - 70:  code prefix match (related discipline) or first_level match
    - 55:  category match
    - 40:  high character overlap (>= 70%)
    - 35:  same 2-digit code field
    - 30:  partial character overlap (2+ chars, >= 40%)
    - 0:   no match
    """
    # Code-based scoring — authoritative when available
    code_score = score_by_code(major_code, code_prefixes)

    if not keyword or not major_name:
        return code_score

    kw = keyword.strip().lower()
    mn = major_name.strip().lower()
    fl = (first_level or "").strip().lower()
    cat = (category or "").strip().lower()

    if kw == mn:
        return max(code_score, 100)
    if kw in mn:
        return max(code_score, 85)

    # Split-keyword fuzzy: "微电子与固体" -> ["微电子","固体"], check if all in major name
    parts = re.split(r"[与和及、，,\s]", kw)
    parts = [p.strip() for p in parts if len(p.strip()) >= 2]
    if len(parts) >= 2 and all(p in mn for p in parts):
        return max(code_score, 90)

    if fl and kw in fl:
        return max(code_score, 70)
    if cat and kw in cat:
        return max(code_score, 55)

    # Character overlap (Jaccard-like)
    kw_chars = set(kw)
    mn_chars = set(mn)
    overlap = len(kw_chars & mn_chars)
    if overlap >= 2:
        ratio = overlap / len(kw_chars)
        if ratio >= 0.7:
            return max(code_score, 40)
        if ratio >= 0.4:
            return max(code_score, 30)
    return code_score


def extract_preferred_majors(profile: dict) -> list[str]:
    """Extract preferred_majors from profile preference_weights."""
    try:
        pw_raw = profile.get("preference_weights", "")
        if pw_raw and isinstance(pw_raw, str):
            pw = json.loads(pw_raw)
        elif isinstance(pw_raw, dict):
            pw = pw_raw
        else:
            return []
        return pw.get("preferred_majors", []) or []
    except (json.JSONDecodeError, TypeError):
        return []


def _resolve_weights(profile: dict) -> dict[str, float | str | list]:
    """Parse preference_weights JSON and return resolved weight values with defaults."""
    pw = {}
    try:
        pw_raw = profile.get("preference_weights", "")
        if pw_raw and isinstance(pw_raw, str):
            pw = json.loads(pw_raw)
        elif isinstance(pw_raw, dict):
            pw = pw_raw
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "w_province": float(pw.get("province_priority", 0.5)),
        "w_level": float(pw.get("level_priority", 0.5)),
        "w_major": float(pw.get("major_priority", 0.5)),
        "w_score": float(pw.get("score_priority", 0.5)),
        "w_major_strength": float(pw.get("major_strength_priority", 0.6)),
        "w_background": float(pw.get("background_priority", 0.5)),
        "risk_tolerance": pw.get("risk_tolerance", "适中"),
        "preferred_cities": pw.get("preferred_cities", []) or [],
        "preferred_majors": pw.get("preferred_majors", []) or [],
    }


def _determine_base_avg(
    school_level: str,
    is_institute: bool,
    re_exam_avg: int,
    recent_avg: int,
    scores: list[int],
    re_scores: list[int],
) -> tuple[float, float]:
    """Determine base cutoff (before tier multiplier) and primary cutoff (after).

    Prefers real 复试线 data, then estimates from 初试 + tier premium.
    Falls back to per-major score averages keyed by (school, major_code).
    Returns (base_avg, primary_avg).
    """
    if re_exam_avg > 0:
        base_avg = float(re_exam_avg)
    elif recent_avg > 0:
        premium = TIER_RE_EXAM_PREMIUM.get(school_level, 0)
        base_avg = float(recent_avg + premium)
    elif scores:
        if re_scores:
            base_avg = sum(re_scores) / len(re_scores)
        else:
            base_avg = sum(scores) / len(scores)
    else:
        base_avg = 0.0

    if is_institute:
        tier_mult = INSTITUTE_TIER_MULTIPLIER
    else:
        tier_mult = TIER_DIFFICULTY_MULTIPLIER.get(school_level, 1.0)
    primary_avg = base_avg * tier_mult

    return base_avg, primary_avg


def _classify_competition(trend: dict) -> str:
    """Classify competition level from admit ratio data."""
    admit_ratio = trend.get("avg_admit_ratio", 0)
    if admit_ratio == 0 and trend.get("applicant_count") and trend.get("admit_count"):
        applicant_count = trend["applicant_count"]
        if applicant_count > 0:
            admit_ratio = trend["admit_count"] / applicant_count
    if admit_ratio > 0 and admit_ratio < 0.1:
        return "竞争激烈"
    elif 0.1 <= admit_ratio < 0.2:
        return "竞争较激烈"
    elif admit_ratio >= 0.2:
        return "竞争中等"
    return "竞争程度未知"


def compute_recommendations(
    profile: dict,
    schools: list[dict],
    score_lines: list[dict],
    trends: list[dict],
    major_keyword: str = "",
    major_lookup: dict[str, dict] | None = None,
    name_to_subjects: dict[tuple[str, str], list[str]] | None = None,
    code_prefixes: dict | None = None,
    background_tier: str = "",
    discipline_rating_lookup: dict[str, int] | None = None,
    risk_direction: str = "",
) -> list[dict]:
    """Two-way weighted scoring: school match + major match, with tier + subject adjustments.

    risk_direction: '' (balanced), '冲刺', '稳妥', or '保底' — controls risk distribution
    of the final top-8 results.
    """
    raw_estimated = profile.get("estimated_score") or 0
    exam_config = profile.get("exam_config", {}) or {}
    estimated = normalize_score(raw_estimated, exam_config)
    target_province = profile.get("target_province", "")
    target_level = profile.get("target_level", "")

    # Fall back to preferred_majors[0], then undergraduate_major
    preferred_majors = extract_preferred_majors(profile)
    if not major_keyword and preferred_majors:
        major_keyword = preferred_majors[0]
    if not major_keyword:
        major_keyword = profile.get("undergraduate_major", "")
    use_major = bool(major_keyword)

    weights = _resolve_weights(profile)
    w_region = float(weights["w_province"])        # → region_fit
    w_level = float(weights["w_level"])            # → level_fit
    w_major = float(weights["w_major"])            # → major_weight in final_match
    w_score_fit = float(weights["w_score"])        # → score_fit
    w_program = float(weights["w_major_strength"])  # → program_strength
    w_background = float(weights["w_background"])   # → background_fit
    risk_tolerance = str(weights["risk_tolerance"])
    preferred_cities: list[str] = list(weights["preferred_cities"]) if isinstance(weights["preferred_cities"], list) else []  # type: ignore[arg-type]
    preferred_majors: list[str] = list(weights["preferred_majors"]) if isinstance(weights["preferred_majors"], list) else []  # type: ignore[arg-type]

    # Derive target_province from preferred_cities if not explicitly set
    if not target_province and preferred_cities:
        target_province = preferred_cities[0]  # Use first preferred city as province

    trend_map: dict[tuple[str, str], dict] = {}
    for t in trends:
        key = (t.get("school_name", ""), t.get("major_name", ""))
        trend_map[key] = t

    school_id_to_name: dict[int, str] = {
        s.get("id"): s.get("name", "")
        for s in schools
        if s.get("id") is not None
    }

    school_scores: dict[tuple[str, str], list[int]] = {}
    school_re_exam_scores: dict[tuple[str, str], list[int]] = {}
    for sl in score_lines:
        sid = sl.get("school_id")
        sname = school_id_to_name.get(sid, str(sid or ""))
        mcode = sl.get("major_code", "")
        key = (sname, mcode)
        school_scores.setdefault(key, []).append(sl.get("total_score", 0))
        re_score = sl.get("re_exam_total_score")
        if re_score:
            school_re_exam_scores.setdefault(key, []).append(re_score)

    # Pre-compute major keyword scores for filtering
    _major_scores: dict[tuple[str, str], int] = {}
    if use_major and major_lookup is not None:
        for (t_sname, mname) in trend_map:
            mdata = major_lookup.get(mname)
            if mdata:
                _major_scores[(t_sname, mname)] = score_major_keyword(
                    major_keyword,
                    mdata.get("name", mname),
                    mdata.get("first_level", ""),
                    mdata.get("category", ""),
                    major_code=mdata.get("code", ""),
                    code_prefixes=code_prefixes,
                )
            else:
                _major_scores[(t_sname, mname)] = 5

    recommendations = []
    for school in schools:
        sname = school.get("name", "")

        for (t_sname, mname), trend in trend_map.items():
            if t_sname != sname:
                continue

            # Skip majors unrelated to keyword (character-overlap < 30)
            if use_major and _major_scores.get((t_sname, mname), 50) < 30:
                continue

            # ── Effective cutoff (tier multiplier + program-specific difficulty) ──
            school_level = school.get("level", "")
            is_institute = is_research_institute(sname)
            re_exam_avg = trend.get("re_exam_avg_score", 0)
            recent_avg = trend.get("recent_avg_score", 0)
            mcode = trend.get("major_code", "")

            scores = school_scores.get((sname, mcode), [])
            re_scores = school_re_exam_scores.get((sname, mcode), [])
            base_avg, _ = _determine_base_avg(
                school_level, is_institute, re_exam_avg, recent_avg, scores, re_scores,
            )

            # Program-difficulty bonus from discipline rating
            if discipline_rating_lookup and sname in discipline_rating_lookup:
                rating_score = discipline_rating_lookup[sname]
                rating_label = _SCORE_TO_RATING.get(rating_score, "")
                prog_diff_bonus = MAJOR_DIFFICULTY_BONUS.get(rating_label, 0.0)
            else:
                prog_diff_bonus = 0.0

            if is_institute:
                tier_mult = INSTITUTE_TIER_MULTIPLIER
            else:
                tier_mult = TIER_DIFFICULTY_MULTIPLIER.get(school_level, 1.0)

            effective_mult = tier_mult + prog_diff_bonus
            effective_cutoff = base_avg * effective_mult if base_avg > 0 else 0

            # ── Six-factor school match ──
            # 1. Score fit (tanh, range ~25-75)
            score_fit_val = _score_component(estimated, effective_cutoff)

            # 2. Program strength (discipline rating, 42-100)
            if discipline_rating_lookup:
                program_strength = discipline_rating_lookup.get(sname, 50)
            else:
                program_strength = 50

            # 3. Background fit: tier gap + 双非红黑榜 + 一志愿保护
            tier_penalty = _tier_gap_penalty(background_tier, school_level)
            dual_penalty = get_dual_non_penalty(sname, school_level, background_tier)
            fc_bonus = _first_choice_bonus_from_admissions(sname, school_level)
            background_fit = max(20, min(100, 70 + dual_penalty + fc_bonus))

            # 4. Region fit
            if target_province and school.get("province") == target_province:
                region_fit = 100
            elif target_province:
                region_fit = 60  # no preference matched, but still open
            else:
                region_fit = 70  # user has no province preference → neutral

            # 5. Level fit
            if target_level and school.get("level") == target_level:
                level_fit = 100
            elif target_level:
                level_fit = 60
            else:
                level_fit = 70  # no level preference → neutral

            # Weighted sum (normalized to 0-100 scale)
            factor_total = w_score_fit + w_program + w_background + w_region + w_level
            if factor_total > 0:
                school_match = int(
                    (score_fit_val * w_score_fit
                     + program_strength * w_program
                     + background_fit * w_background
                     + region_fit * w_region
                     + level_fit * w_level)
                    / factor_total
                )
            else:
                school_match = 50

            # Apply tier gap penalty (separate from background_fit to keep weights clean)
            school_match = max(10, min(100, school_match - tier_penalty))

            # ── Background-aware risk classification ──
            risk_shift = _background_risk_shift(background_tier, school_level)
            risk_diff = (estimated - effective_cutoff + risk_shift) if estimated > 0 and effective_cutoff > 0 else 0
            margin = 10 if risk_tolerance == "激进" else 20 if risk_tolerance == "保守" else 15
            if risk_diff > margin:
                risk = "保底"
            elif risk_diff < -margin:
                risk = "冲刺"
            else:
                risk = "稳妥"

            # -- Major match score (0-100) --
            if use_major:
                major_score = _major_scores.get((t_sname, mname), 5)
            else:
                major_score = 50  # neutral when no keyword

            # Classify major match quality for UI
            if major_score >= 85:
                major_match_level = "exact"       # 精准匹配
            elif major_score >= 55:
                major_match_level = "related"      # 同门类相关
            elif major_score >= 30:
                major_match_level = "weak"         # 弱相关/跨方向
            else:
                major_match_level = "unrelated"    # 不相关（不应出现，已在上层过滤）

            # -- Combined final score --
            if use_major:
                major_weight = 0.35 + w_major * 0.3  # range 0.35-0.65
                final_match = int(school_match * (1 - major_weight) + major_score * major_weight)
            else:
                final_match = school_match

            # -- Subject compatibility penalty --
            subject_penalty, subject_warnings = 0, []
            if exam_config and name_to_subjects:
                major_code = trend.get("major_code", "")
                school_subjs = name_to_subjects.get((sname, major_code))
                subject_penalty, subject_warnings = check_subject_compatibility(
                    exam_config, school_subjs,
                )
                final_match = max(5, final_match + subject_penalty)

            competition = _classify_competition(trend)
            score_trend = trend.get("trend_analysis", "")

            recommendations.append({
                "school_name": sname,
                "school_province": school.get("province", ""),
                "school_level": school.get("level", ""),
                "school_type": school.get("school_type", ""),
                "school_description": (school.get("description") or "")[:200],
                "ranking_national": school.get("ranking_national"),
                "major_name": mname,
                "major_code": trend.get("major_code", ""),
                "risk_level": risk,
                "match_score": final_match,
                "score_trend": score_trend,
                "competition": competition,
                "recent_avg_score": int(effective_cutoff) if effective_cutoff else 0,
                "re_exam_avg_score": int(base_avg) if base_avg else 0,
                "normalized_score": estimated,
                "subject_warnings": subject_warnings,
                "major_match_level": major_match_level,
                "is_research_institute": is_institute,
                "major_strength_score": program_strength,
                "major_strength_label": _score_to_strength_label(program_strength),
                "admissions_summary": get_admissions_summary(sname, school_level),
            })

    recommendations.sort(key=lambda r: r["match_score"], reverse=True)
    return _rebalance_risk_distribution(recommendations, risk_direction, top_n=8)


def find_school_name(school_id, schools: list[dict]) -> str:
    for s in schools:
        if s.get("id") == school_id or s.get("school_id") == school_id:
            return s.get("name", "")
    return str(school_id)


def build_profile_dict(profile: UserProfile, province: str = "", level: str = "") -> dict:
    """Build a profile dict for the scoring pipeline from a UserProfile model."""
    exam_config = {}
    if profile.exam_config:
        try:
            exam_config = json.loads(profile.exam_config)
        except (json.JSONDecodeError, TypeError):
            pass
    strengths = {}
    if profile.subject_strengths:
        try:
            strengths = json.loads(profile.subject_strengths)
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": profile.id,
        "undergraduate_school": profile.undergraduate_school or "",
        "undergraduate_major": profile.undergraduate_major or "",
        "estimated_score": profile.estimated_score,
        "target_province": province or "",
        "target_level": level or "",
        "available_hours_per_day": profile.available_hours_per_day,
        "exam_year": profile.exam_year,
        "notes": profile.notes or "",
        "exam_config": exam_config,
        "subject_strengths": strengths,
        "preference_weights": profile.preference_weights or "",
    }


def build_major_lookup(db: Session, major_keyword: str) -> dict[str, dict]:
    """Build major_lookup dict for a keyword; returns empty dict if no keyword."""
    major_lookup: dict[str, dict] = {}
    if not major_keyword or not major_keyword.strip():
        return major_lookup
    kw = major_keyword.strip()
    matching_majors = list(
        db.execute(
            select(Major).where(
                or_(
                    Major.name.ilike(f"%{kw}%"),
                    Major.discipline.ilike(f"%{kw}%"),
                    Major.category.ilike(f"%{kw}%"),
                )
            ).limit(500)
        ).scalars().all()
    )
    for m in matching_majors:
        if m.name not in major_lookup:
            major_lookup[m.name] = {
                "name": m.name,
                "first_level": m.discipline or "",
                "category": m.category or "",
                "code": m.code,
                "degree_level": m.degree_type or "",
            }
        # Also index by code so trends using raw code as name are found
        if m.code and m.code not in major_lookup:
            major_lookup[m.code] = {
                "name": m.name,
                "first_level": m.discipline or "",
                "category": m.category or "",
                "code": m.code,
                "degree_level": m.degree_type or "",
            }
    return major_lookup


def build_exam_subjects_lookup(
    db: Session, major_keys: set[tuple[int, str]]
) -> dict[tuple[int, str], str]:
    """Build (school_id, major_code) → exam_subjects lookup via SchoolMajor."""
    exam_subjects_lookup: dict[tuple[int, str], str] = {}
    if not major_keys:
        return exam_subjects_lookup
    conditions = [
        (SchoolMajor.school_id == sid) & (SchoolMajor.major.has(Major.code == mcode))
        for sid, mcode in major_keys
    ]
    for i in range(0, len(conditions), 400):
        chunk = conditions[i:i + 400]
        for sm in db.execute(
            select(SchoolMajor).join(Major).where(or_(*chunk))
        ).scalars().all():
            key = (sm.school_id, sm.major.code)
            if key not in exam_subjects_lookup:
                subjects = [sm.exam_politics, sm.exam_english, sm.exam_math,
                           sm.exam_course1_name, sm.exam_course2_name, sm.exam_course3_name]
                exam_subjects_lookup[key] = json.dumps([s for s in subjects if s], ensure_ascii=False)
    return exam_subjects_lookup


def build_name_to_subjects(
    exam_subjects_lookup: dict[tuple[int, str], str],
    schools: list[School],
) -> dict[tuple[str, str], list[str]]:
    """Convert (school_id, code) → json_str to (school_name, code) → list[str]."""
    name_to_subjects: dict[tuple[str, str], list[str]] = {}
    for (sid, mcode), subj_str in exam_subjects_lookup.items():
        sname = next((s.name for s in schools if s.id == sid), "")
        if sname and subj_str:
            try:
                name_to_subjects[(sname, mcode)] = (
                    json.loads(subj_str)
                    if isinstance(subj_str, str) and subj_str.startswith("[")
                    else [subj_str]
                )
            except json.JSONDecodeError:
                name_to_subjects[(sname, mcode)] = [subj_str]
    return name_to_subjects


def build_discipline_rating_lookup(
    db: Session,
    code_prefixes: dict | None,
) -> dict[str, int]:
    """Build school_name → best_numeric_score lookup for matched disciplines.

    Queries discipline_ratings for all discipline codes matching the user's
    target major keyword (primary + related prefixes). Returns a dict mapping
    school_name to the BEST (highest) numeric score among all matching
    disciplines for that school. Schools without ratings get 50 (neutral).
    """
    if not code_prefixes:
        return {}
    all_codes: set[str] = set()
    all_codes.update(code_prefixes.get("primary", set()))
    all_codes.update(code_prefixes.get("related", set()))
    if not all_codes:
        return {}

    from app.models import DisciplineRating

    rows = db.execute(
        select(DisciplineRating).where(
            DisciplineRating.discipline_code.in_(list(all_codes))
        )
    ).scalars().all()

    lookup: dict[str, int] = {}
    for row in rows:
        score = RATING_TO_SCORE.get(row.rating, 50)
        if row.school_name not in lookup or score > lookup[row.school_name]:
            lookup[row.school_name] = score
    return lookup


def _rebalance_risk_distribution(
    recommendations: list[dict],
    risk_direction: str = "",
    top_n: int = 8,
) -> list[dict]:
    """Rebalance recommendations by risk level.

    Default (no direction): 保底 3-4, 稳妥 2-3, 冲刺 2
    With direction: 1 from each non-selected direction, rest from selected.
    """
    保底 = [r for r in recommendations if r["risk_level"] == "保底"]
    稳妥 = [r for r in recommendations if r["risk_level"] == "稳妥"]
    冲刺 = [r for r in recommendations if r["risk_level"] == "冲刺"]

    if risk_direction == "冲刺":
        result = 保底[:1] + 稳妥[:1] + 冲刺[:top_n - 2]
    elif risk_direction == "保底":
        result = 冲刺[:1] + 稳妥[:1] + 保底[:top_n - 2]
    elif risk_direction == "稳妥":
        result = 冲刺[:1] + 保底[:1] + 稳妥[:top_n - 2]
    else:
        # Default balanced: 保底 4, 稳妥 3, 冲刺 2 (total target 9, capped at top_n)
        result = 保底[:3] + 稳妥[:3] + 冲刺[:2]
        # Fill remaining slots from overall sorted list if any category is short
        seen = {(r["school_name"], r["major_code"]) for r in result}
        for r in recommendations:
            if len(result) >= top_n:
                break
            if (r["school_name"], r["major_code"]) not in seen:
                result.append(r)

    result.sort(key=lambda r: r["match_score"], reverse=True)
    return result[:top_n]


def _score_to_strength_label(score: int) -> str:
    if score >= 92:
        return "学科顶尖"
    if score >= 85:
        return "学科很强"
    if score >= 70:
        return "学科较强"
    if score >= 55:
        return "学科一般"
    return "学科数据不足"


def build_recommendation_items(
    precomputed: list[dict],
    pros_by_idx: dict[int, dict],
) -> list[RecommendationItem]:
    """Convert precomputed dicts to RecommendationItem list with pros/cons."""
    return [
        RecommendationItem(
            school_name=r["school_name"],
            school_province=r["school_province"],
            school_level=r["school_level"],
            school_type=r.get("school_type", ""),
            school_description=r.get("school_description", ""),
            ranking_national=r.get("ranking_national"),
            major_name=r["major_name"],
            major_code=r["major_code"],
            risk_level=r["risk_level"],
            match_score=r["match_score"],
            score_trend=r["score_trend"],
            competition=r["competition"],
            re_exam_avg_score=float(r.get("re_exam_avg_score", 0)),
            pros=pros_by_idx.get(i + 1, {}).get("pros", []),
            cons=pros_by_idx.get(i + 1, {}).get("cons", []),
            subject_warnings=r.get("subject_warnings", []),
            major_match_level=r.get("major_match_level", ""),
            is_research_institute=r.get("is_research_institute", False),
            major_strength_score=float(r.get("major_strength_score", 50)),
            major_strength_label=r.get("major_strength_label", ""),
            admissions_summary=r.get("admissions_summary", ""),
        )
        for i, r in enumerate(precomputed)
    ]
