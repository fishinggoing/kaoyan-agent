# kaoyan_agent/collector/yanzhao.py
import sqlite3
import json
from anthropic import Anthropic
from kaoyan_agent.collector.base import WebCollector, CollectResult
from kaoyan_agent.collector.parser import parse_with_claude


# 研招网公开入口
YANZHAO_BASE = "https://yz.chsi.com.cn"


class YanZhaoCollector(WebCollector):
    def __init__(self, conn: sqlite3.Connection, client: Anthropic, timeout: int = 30):
        super().__init__(conn, timeout)
        self.llm = client

    def collect_school_info(self, school_name: str) -> CollectResult:
        """Search 研招网 for a school and collect its data."""
        result = CollectResult(success=False)

        try:
            # 研招网院校信息查询 API
            search_url = f"{YANZHAO_BASE}/zyk/schoolPage/schoolPage.action?dwmc={school_name}"
            html = self.fetch(search_url)

            parsed = parse_with_claude(self.llm, html, url=search_url)

            if parsed.get("_parse_error"):
                result.errors.append(f"Parse warning: {parsed['_parse_error'][:200]}")

            # Write schools
            for school in parsed.get("schools", []):
                if not self._school_exists(school["name"]):
                    self._insert_school(school)
                    result.schools_added += 1

            # Write majors
            for major in parsed.get("majors", []):
                school_id = self._get_school_id(major.get("school_name", school_name))
                if school_id and not self._major_exists(school_id, major["name"]):
                    self._insert_major(school_id, major)
                    result.majors_added += 1

            # Write scores
            for score in parsed.get("admission_scores", []):
                school_id = self._get_school_id(score.get("school_name", school_name))
                major_id = self._get_major_id(school_id, score.get("major_name", ""))
                if major_id and not self._score_exists(major_id, score.get("year", 2025)):
                    self._insert_score(major_id, score)
                    result.scores_added += 1

            # Write employment
            for emp in parsed.get("employment", []):
                school_id = self._get_school_id(emp.get("school_name", school_name))
                if school_id:
                    self._insert_employment(school_id, emp)

            self.conn.commit()
            result.success = result.schools_added > 0 or result.majors_added > 0

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _school_exists(self, name: str) -> bool:
        cursor = self.conn.execute("SELECT id FROM schools WHERE name=?", (name,))
        return cursor.fetchone() is not None

    def _get_school_id(self, name: str) -> int | None:
        cursor = self.conn.execute("SELECT id FROM schools WHERE name=?", (name,))
        row = cursor.fetchone()
        return row[0] if row else None

    def _insert_school(self, school: dict):
        self.conn.execute(
            "INSERT INTO schools (name, tier, province, city, type) VALUES (?,?,?,?,?)",
            (
                school.get("name", ""),
                school.get("tier", ""),
                school.get("province", ""),
                school.get("city", ""),
                school.get("type", ""),
            ),
        )

    def _major_exists(self, school_id: int, name: str) -> bool:
        cursor = self.conn.execute(
            "SELECT id FROM majors WHERE school_id=? AND name=?", (school_id, name)
        )
        return cursor.fetchone() is not None

    def _get_major_id(self, school_id: int | None, name: str) -> int | None:
        if not school_id:
            return None
        cursor = self.conn.execute(
            "SELECT id FROM majors WHERE school_id=? AND name=?", (school_id, name)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _insert_major(self, school_id: int, major: dict):
        exam_subjects = json.dumps(
            major.get("exam_subjects", []), ensure_ascii=False
        )
        self.conn.execute(
            "INSERT INTO majors (school_id, name, discipline_rank, exam_subjects) VALUES (?,?,?,?)",
            (school_id, major.get("name", ""), major.get("discipline_rank", ""), exam_subjects),
        )

    def _score_exists(self, major_id: int, year: int) -> bool:
        cursor = self.conn.execute(
            "SELECT id FROM admission_scores WHERE major_id=? AND year=?", (major_id, year)
        )
        return cursor.fetchone() is not None

    def _insert_score(self, major_id: int, score: dict):
        self.conn.execute(
            """INSERT INTO admission_scores
            (major_id, year, admission_line, applicants, enrolled, push_free_ratio)
            VALUES (?,?,?,?,?,?)""",
            (
                major_id,
                score.get("year", 2025),
                score.get("admission_line"),
                score.get("applicants"),
                score.get("enrolled"),
                score.get("push_free_ratio"),
            ),
        )

    def _insert_employment(self, school_id: int, emp: dict):
        self.conn.execute(
            """INSERT OR IGNORE INTO employment_quality
            (school_id, year, employment_rate, avg_salary, summary)
            VALUES (?,?,?,?,?)""",
            (
                school_id,
                emp.get("year", 2024),
                emp.get("employment_rate"),
                emp.get("avg_salary"),
                emp.get("summary", ""),
            ),
        )
