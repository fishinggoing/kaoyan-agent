"""Tests for agent parsing logic (no real API calls — mocked via conftest)."""

import json
from app.agents.orchestrator import OrchestratorAgent, DecisionResult, RecommendationItem
from app.config import settings


# ── OrchestratorAgent ──

class TestOrchestratorParsing:
    def test_parse_valid_recommendations(self, mock_openai):
        response = json.dumps({
            "recommendations": [
                {
                    "school_name": "清华大学",
                    "school_province": "北京",
                    "school_level": "C9",
                    "major_name": "计算机科学与技术",
                    "major_code": "081200",
                    "risk_level": "冲刺",
                    "match_score": 75,
                    "score_trend": "逐年上升",
                    "competition": "竞争激烈",
                    "pros": ["学术实力强", "就业好"],
                    "cons": ["分数线高"],
                }
            ],
            "analysis": "该考生有冲击名校的潜力",
            "plan_suggestion": "建议加强数学和专业课复习",
        })
        mock_openai.chat.completions.create.return_value.choices[0].message.content = response

        agent = OrchestratorAgent()
        result = agent._parse_response(response)

        assert len(result.recommendations) == 1
        assert result.recommendations[0].school_name == "清华大学"
        assert result.recommendations[0].risk_level == "冲刺"
        assert result.recommendations[0].match_score == 75
        assert len(result.recommendations[0].pros) == 2
        assert len(result.recommendations[0].cons) == 1
        assert "冲击名校" in result.analysis
        assert "加强数学" in result.plan_suggestion

    def test_parse_multiple_recommendations(self, mock_openai):
        response = json.dumps({
            "recommendations": [
                {"school_name": "A大学", "school_province": "北京", "school_level": "985",
                 "major_name": "CS", "major_code": "01", "risk_level": "冲刺",
                 "match_score": 70, "score_trend": "上升", "competition": "激烈",
                 "pros": [], "cons": []},
                {"school_name": "B大学", "school_province": "上海", "school_level": "211",
                 "major_name": "CS", "major_code": "01", "risk_level": "稳妥",
                 "match_score": 85, "score_trend": "稳定", "competition": "中等",
                 "pros": [], "cons": []},
                {"school_name": "C大学", "school_province": "广东", "school_level": "双一流",
                 "major_name": "CS", "major_code": "01", "risk_level": "保底",
                 "match_score": 92, "score_trend": "下降", "competition": "较低",
                 "pros": [], "cons": []},
            ],
            "analysis": "综合分析",
            "plan_suggestion": "备考建议",
        })

        agent = OrchestratorAgent()
        result = agent._parse_response(response)

        assert len(result.recommendations) == 3
        risk_levels = [r.risk_level for r in result.recommendations]
        assert "冲刺" in risk_levels
        assert "稳妥" in risk_levels
        assert "保底" in risk_levels

    def test_parse_invalid_json(self):
        agent = OrchestratorAgent()
        result = agent._parse_response("not json at all")

        assert result.recommendations == []
        assert result.analysis == "not json at all"

    def test_parse_empty_json(self):
        agent = OrchestratorAgent()
        result = agent._parse_response("{}")

        assert result.recommendations == []
        assert result.analysis == ""

    def test_parse_missing_fields_defaults(self):
        response = json.dumps({
            "recommendations": [
                {"school_name": "X大学"}
            ],
            "analysis": "",
            "plan_suggestion": "",
        })

        agent = OrchestratorAgent()
        result = agent._parse_response(response)

        rec = result.recommendations[0]
        assert rec.school_name == "X大学"
        assert rec.match_score == 70  # default
        assert rec.risk_level == "稳妥"  # default
        assert rec.pros == []

    def test_build_prompt_structure(self):
        agent = OrchestratorAgent()
        prompt = agent._build_prompt(
            profile={"undergraduate_school": "测试大学", "estimated_score": 370},
            schools=[{"name": "清华", "province": "北京", "level": "C9"}],
            score_data=[{"year": 2025, "total_score": 360}],
            trends=[{"school_name": "清华", "trend_analysis": "上升趋势"}],
        )
        assert "测试大学" in prompt
        assert "清华" in prompt
        assert "360" in prompt
        assert "上升趋势" in prompt

    def test_recommendation_dataclass(self):
        rec = RecommendationItem(
            school_name="测试大学",
            school_province="北京",
            school_level="985",
            major_name="CS",
            major_code="01",
            risk_level="稳妥",
            match_score=80.5,
            score_trend="稳定",
            competition="中等",
            pros=["优势1"],
            cons=[],
        )
        assert rec.school_name == "测试大学"
        assert rec.match_score == 80.5
