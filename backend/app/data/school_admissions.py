"""
School admissions characteristics: re-exam ratio, first-choice protection, 双非-friendliness.

Data sourced from 2025 admissions handbooks, candidate reports, and public announcements.
Covers ~80 schools with confirmed data; remaining schools use tier-based defaults.
"""

# ── Re-exam ratio buckets ────────────────────────────────────────────────────
RE_EXAM_LOW = "30%"
RE_EXAM_MODERATE = "40%"
RE_EXAM_HIGH = "50%"
RE_EXAM_VERY_HIGH = "60%+"

# ── Tier-based defaults (used when no school-specific data) ───────────────────
TIER_DEFAULT_RE_EXAM: dict[str, str] = {
    "C9": "50%",
    "985": "40-50%",
    "211": "40%",
    "双一流": "40%",
    "普本": "30-40%",
}


def _b(
    re_exam_ratio: str,
    protect_first_choice: bool | None = None,
    dual_non_friendly: bool | None = None,
    notes: str = "",
) -> dict:
    """Builder helper for school admissions records."""
    return {
        "re_exam_ratio": re_exam_ratio,
        "protect_first_choice": protect_first_choice,
        "dual_non_friendly": dual_non_friendly,
        "notes": notes,
    }


# ── School-specific admissions data ───────────────────────────────────────────
# dual_non_friendly: True=黑榜(双非不友好), False=红榜(双非友好), None=未知

SCHOOL_ADMISSIONS: dict[str, dict] = {
    # ═══ C9 高校 ═══
    "北京大学": _b("30-50%", notes="各院系差异大，光华30%，软微40%"),
    "清华大学": _b("50%", notes="复试权重高，注重科研潜力"),
    "哈尔滨工业大学": _b("50%", True, False, "匿名抽签复试，初试占比高，流程透明"),
    "浙江大学": _b("50-60%", None, True, "计算机新增项目路演，考生反馈存在第一学历歧视"),
    "复旦大学": _b("50%", None, False, "复试出成绩快，无院校歧视"),
    "上海交通大学": _b("50%", None, False, "无院校/学历歧视"),
    "南京大学": _b("50%", True, False, "保护一志愿，复试不问本科背景"),
    "中国科学技术大学": _b("40%", None, False, "复试比1:1.2，专业课不压分"),
    "西安交通大学": _b("50%", None, None),

    # ═══ 985 高校 ═══
    "四川大学": _b("50%", True, False, "经济学院2025年复试提至50%，海纳百川不歧视"),
    "武汉大学": _b("50%", None, None),
    "华中科技大学": _b("50%", None, False, "不歧视本科出身"),
    "中山大学": _b("50%", None, None),
    "吉林大学": _b("40%", None, False, "初试占60-70%，复试时间早，不歧视"),
    "南开大学": _b("40%", None, False, "复试次日出结果，匿名考核"),
    "东南大学": _b("50%", True, False, "保护一志愿，初试占比50-70%，不接受校外调剂"),
    "中南大学": _b("50%", True, False, "保护一志愿，二本生录取率超40%，不接受校外调剂"),
    "北京师范大学": _b("50%", True, False, "上午复试下午公示，部分专业全面试，只接校内调剂"),
    "厦门大学": _b("50%", None, False, "初试占比高，复试内容常规化"),
    "大连理工大学": _b("40%", True, False, "不歧视双非，复试出成绩快，保护一志愿"),
    "华南理工大学": _b("40-50%", None, False, "不歧视本科出身，招生人数多"),
    "电子科技大学": _b("50%", None, False, "不歧视不排外，初试不压分"),
    "中央民族大学": _b("40%", True, False, "教育学双非通过率92%，保护一志愿"),
    "山东大学": _b("50%", None, True, "调剂时有倾向985/211生源的反馈"),
    "兰州大学": _b("50%", None, True, "调剂优先985/211，奖学金本科权重60%"),
    "中国海洋大学": _b("40%", None, None),
    "西北工业大学": _b("50%", None, None),
    "中国人民大学": _b("50%", None, None),
    "同济大学": _b("50%", None, None),
    "北京航空航天大学": _b("50%", None, None),
    "北京理工大学": _b("50%", None, None),
    "中国农业大学": _b("40%", None, None),
    "华东师范大学": _b("50%", None, None),
    "天津大学": _b("50%", None, None),
    "重庆大学": _b("50%", None, None),
    "东北大学": _b("40%", None, None),
    "湖南大学": _b("50%", None, None),
    "西北农林科技大学": _b("40%", None, None),

    # ═══ 211 高校 ═══
    "中央财经大学": _b("30%", True, False, "金融专硕初试占80%，双非录取率52%，不接受校外调剂"),
    "上海财经大学": _b("40%", True, False, "复试双盲评审，保护一志愿，不接受校外调剂"),
    "对外经济贸易大学": _b("40%", True, False, "复试比1:1.2，不接受校外调剂，保护一志愿"),
    "暨南大学": _b("50%", True, False, "不接收校外调剂，数据透明，真题公开"),
    "中南财经政法大学": _b("40%", None, False, "不歧视本科出身，专业课不压分"),
    "西南财经大学": _b("30%", None, False, "初试占比70%，不歧视，专业课不压分"),
    "上海外国语大学": _b("40%", True, False, "匿名复试，双非生占比60%，保护一志愿"),
    "东华大学": _b("40%", True, False, "保护一志愿，不接受校外调剂"),
    "福州大学": _b("40%", True, False, "不歧视双非，保护一志愿"),
    "辽宁大学": _b("30%", True, False, "初试70%，复试隔天出成绩，不接受校外调剂"),
    "南昌大学": _b("40%", True, False, "保护一志愿，复试淘汰率低于10%"),
    "河海大学": _b("40%", None, False, "不歧视本科出身，专业课不压分"),
    "华中农业大学": _b("40%", True, False, "保护一志愿，不歧视本科"),
    "南京理工大学": _b("50%", None, True, "热门专业调剂优先985/211，双非需分显著高于线"),
    "哈尔滨工程大学": _b("50%", None, True, "争议校，曾有211需305双非需350的案例"),
    "苏州大学": _b("50%", None, True, "考生反馈存在第一学历歧视"),
    "南京师范大学": _b("50%", None, True, "有歧视双非的评价"),
    "西南交通大学": _b("50%", None, True, "调剂对本科背景有隐性偏好"),
    "广西大学": _b("40%", None, True, "多名考生反馈调剂阶段临时取消双非复试资格"),
    "华南师范大学": _b("40%", False, None, "一志愿考生不享有优先录取"),
    "华中师范大学": _b("50%", False, None, "一志愿和调剂生混合排名"),
    "云南大学": _b("40%", False, None, "调剂门槛高，985/211优先"),
    "安徽大学": _b("40%", None, None, "专业课压分严重，为调剂优质生源腾名额"),
    "江南大学": _b("40%", False, None, "不保护一志愿"),
    "中国传媒大学": _b("50%", False, None, "一志愿与调剂生统一排名"),
    "上海大学": _b("40%", None, None),
    "北京科技大学": _b("40%", None, None),
    "北京邮电大学": _b("40-50%", None, None),
    "西安电子科技大学": _b("40%", None, None),
    "南京航空航天大学": _b("50%", None, None),
    "武汉理工大学": _b("40%", None, None),
    "北京交通大学": _b("40%", None, None),
    "华东理工大学": _b("40%", None, None),
    "北京工业大学": _b("40%", None, None),
    "郑州大学": _b("40%", None, None),
    "西南大学": _b("40%", None, None),

    # ═══ 双一流 ═══
    "中国科学院大学": _b("50%", None, None, "复试要求高，注重科研背景"),
    "南方科技大学": _b("50%", None, None),
    "上海科技大学": _b("50%", None, None),
    "南京邮电大学": _b("40%", None, None),
    "南京信息工程大学": _b("40%", None, None),
    "南方医科大学": _b("40%", None, None),
    "湘潭大学": _b("40%", None, None),
    "河南大学": _b("40%", None, None),
    "宁波大学": _b("40%", None, None),
    "首都师范大学": _b("40%", None, None),

    # ═══ 普本 ═══
    "深圳大学": _b("40%", False, None, "一志愿与调剂生统一排名"),
}


def lookup(school_name: str, school_level: str = "") -> dict:
    """Get admissions data for a school, falling back to tier defaults."""
    if school_name in SCHOOL_ADMISSIONS:
        return SCHOOL_ADMISSIONS[school_name]
    ratio = TIER_DEFAULT_RE_EXAM.get(school_level, "40%")
    return {
        "re_exam_ratio": ratio,
        "protect_first_choice": None,
        "dual_non_friendly": None,
        "notes": "",
    }


def is_high_re_exam(re_exam_ratio: str) -> bool:
    """Check if re-exam ratio qualifies as 'high' (≥50%)."""
    if not re_exam_ratio:
        return False
    ratios = re_exam_ratio.replace("%", "").split("-")
    try:
        high_val = max(int(r) for r in ratios)
        return high_val >= 50
    except ValueError:
        return False


def get_dual_non_penalty(
    school_name: str,
    school_level: str,
    background_tier: str,
) -> int:
    """Calculate 双非降权 penalty for a target school given user's undergrad tier.

    Only applies when:
    - User's undergrad is 普本 or 双一流 (non-elite background)
    - School has high re-exam ratio (≥50%) — where interview bias matters most
    - School is on the blacklist (confirmed 双非不友好) or unknown

    Returns negative penalty (0 to -15).
    """
    if background_tier not in ("普本", "双一流"):
        return 0

    data = lookup(school_name, school_level)
    ratio = data.get("re_exam_ratio", "40%")
    dual = data.get("dual_non_friendly")

    # Redlist schools (confirmed friendly) — no penalty
    if dual is False:
        return 0

    high = is_high_re_exam(ratio)

    if high and dual is True:
        # Blacklisted + high re-exam ratio → strong penalty
        return -12
    elif high:
        # Unknown + high re-exam ratio (C9/985 default) → moderate penalty
        return -5
    elif dual is True:
        # Blacklisted but moderate re-exam ratio → mild penalty
        return -7
    return 0


def get_admissions_summary(school_name: str, school_level: str = "") -> str:
    """Generate a concise admissions summary for LLM prompts."""
    data = lookup(school_name, school_level)
    parts = [f"复试占比: {data['re_exam_ratio']}"]

    pfc = data.get("protect_first_choice")
    if pfc is True:
        parts.append("保护一志愿: 是")
    elif pfc is False:
        parts.append("保护一志愿: 否(一志愿与调剂生混合排名)")

    dual = data.get("dual_non_friendly")
    if dual is True:
        parts.append("双非友好度: 不友好(有双非歧视反馈)")
    elif dual is False:
        parts.append("双非友好度: 友好(不歧视本科出身)")

    if data.get("notes"):
        parts.append(data["notes"])

    return "；".join(parts)
