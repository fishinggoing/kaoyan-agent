"""Integration tests for profile API endpoints."""


class TestCreateProfile:
    def test_create_valid(self, client, test_headers):
        resp = client.post("/api/profiles/", json={
            "nickname": "测试考生",
            "undergraduate_school": "某大学",
            "estimated_score": 380,
            "available_hours_per_day": 6,
            "exam_year": 2026,
        }, headers=test_headers)
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["nickname"] == "测试考生"
        assert data["data"]["id"] is not None


class TestGetProfile:
    def test_get_existing(self, client, sample_profile, test_headers):
        resp = client.get(f"/api/profiles/{sample_profile.id}", headers=test_headers)
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["nickname"] == "测试考生"
        assert data["data"]["estimated_score"] == 370

    def test_get_not_found(self, client, test_headers):
        resp = client.get("/api/profiles/99999", headers=test_headers)
        assert resp.status_code == 404


class TestUpdateProfile:
    def test_update_valid(self, client, sample_profile, test_headers):
        resp = client.put(f"/api/profiles/{sample_profile.id}", json={
            "estimated_score": 400,
            "notes": "更新后的备注",
        }, headers=test_headers)
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["estimated_score"] == 400
        assert data["data"]["notes"] == "更新后的备注"
