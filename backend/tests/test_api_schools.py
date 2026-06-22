"""Integration tests for school API endpoints."""

import json


class TestListSchools:
    def test_list_all(self, client, sample_schools):
        resp = client.get("/api/schools/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] == 4

    def test_list_with_pagination(self, client, sample_schools):
        resp = client.get("/api/schools/?page=1&size=2")
        data = resp.json()
        assert len(data["data"]["items"]) == 2
        assert data["data"]["total"] == 4

    def test_list_by_province(self, client, sample_schools):
        resp = client.get("/api/schools/?province=北京")
        data = resp.json()
        assert data["success"] is True
        for item in data["data"]["items"]:
            assert item["province"] == "北京"

    def test_list_by_level(self, client, sample_schools):
        resp = client.get("/api/schools/?level=C9")
        data = resp.json()
        assert data["success"] is True

    def test_list_by_name_search(self, client, sample_schools):
        resp = client.get("/api/schools/?name=浙江")
        data = resp.json()
        assert data["success"] is True
        assert any("浙江" in s["name"] for s in data["data"]["items"])


class TestGetSchool:
    def test_get_existing(self, client, sample_school):
        resp = client.get(f"/api/schools/{sample_school.id}")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == "清华大学"

    def test_get_not_found(self, client):
        resp = client.get("/api/schools/99999")
        assert resp.status_code == 404


class TestCreateSchool:
    def test_create_valid(self, client):
        resp = client.post("/api/schools/", json={
            "name": "同济大学",
            "province": "上海",
            "city": "上海",
            "level": "985",
            "school_type": "理工",
            "is_graduate_school": True,
            "ranking_national": 15,
        })
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == "同济大学"
        assert data["data"]["id"] is not None


class TestUpdateSchool:
    def test_update_valid(self, client, sample_school):
        resp = client.put(f"/api/schools/{sample_school.id}", json={
            "description": "更新描述",
        })
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["description"] == "更新描述"

    def test_update_not_found(self, client):
        resp = client.put("/api/schools/99999", json={"description": "x"})
        assert resp.status_code == 404


class TestSearchSchools:
    def test_search(self, client, sample_schools):
        resp = client.get("/api/schools/search?q=浙江")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] >= 1
        assert any("浙江" in s["name"] for s in data["data"]["items"])

    def test_search_empty(self, client, sample_schools):
        resp = client.get("/api/schools/search?q=")
        data = resp.json()
        assert data["success"] is True

    def test_search_no_results(self, client):
        resp = client.get("/api/schools/search?q=xyzabc123")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0


class TestDeleteSchool:
    def test_delete(self, client, sample_school):
        school_id = sample_school.id
        resp = client.delete(f"/api/schools/{school_id}")
        assert resp.json()["success"] is True

        # Verify deleted
        resp2 = client.get(f"/api/schools/{school_id}")
        assert resp2.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/schools/99999")
        assert resp.status_code == 404
