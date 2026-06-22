"""Integration tests for score lines and decisions API endpoints."""


class TestScoreLines:
    def test_list_all(self, client, sample_score_lines):
        resp = client.get("/api/score-lines/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] == 5

    def test_list_by_year(self, client, sample_score_lines):
        resp = client.get("/api/score-lines/?year=2025")
        data = resp.json()
        assert data["data"]["total"] == 1

    def test_trend(self, client, sample_school, sample_major, sample_score_lines):
        resp = client.get(
            f"/api/score-lines/trend?school_id={sample_school.id}&major_code={sample_major.code}"
        )
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["school_name"] == "清华大学"
        assert len(data["data"]["data_points"]) == 5

    def test_trend_missing_params(self, client):
        resp = client.get("/api/score-lines/trend?school_id=1")
        assert resp.status_code == 422  # major_code is required


class TestDecisions:
    def test_recommend_missing_profile(self, client, test_headers):
        resp = client.post("/api/decisions/recommend", json={}, headers=test_headers)
        assert resp.status_code == 422  # Pydantic validation error

    def test_recommend_profile_not_found(self, client, test_headers):
        resp = client.post("/api/decisions/recommend", json={"profile_id": 99999}, headers=test_headers)
        data = resp.json()
        assert data["success"] is True  # API returns 200 with empty result
        assert "未找到考生画像" in data["data"]["analysis"]

    def test_recommend_with_profile(self, client, sample_profile, sample_school,
                                     sample_major, sample_score_lines, test_headers):
        """Recommendation with valid profile — will be mocked."""
        resp = client.post("/api/decisions/recommend", json={"profile_id": sample_profile.id}, headers=test_headers)
        data = resp.json()
        assert data["success"] is True
        assert "recommendations" in data["data"]
