"""Integration tests for major API endpoints."""


class TestListMajors:
    def test_list_all(self, client, sample_major):
        resp = client.get("/api/majors/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] >= 1

    def test_list_by_name(self, client, sample_major):
        resp = client.get("/api/majors/?name=计算机")
        data = resp.json()
        assert data["success"] is True
        assert any("计算机" in m["name"] for m in data["data"]["items"])

    def test_list_by_code(self, client, sample_major):
        resp = client.get("/api/majors/?code=0812")
        data = resp.json()
        assert data["success"] is True

    def test_list_by_category(self, client, sample_major):
        resp = client.get("/api/majors/?category=工学")
        data = resp.json()
        assert data["success"] is True


class TestGetMajor:
    def test_get_existing(self, client, sample_major):
        resp = client.get(f"/api/majors/{sample_major.id}")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == "计算机科学与技术"
        assert data["data"]["school_name"] == "清华大学"

    def test_get_not_found(self, client):
        resp = client.get("/api/majors/99999")
        assert resp.status_code == 404


class TestCategories:
    def test_list_categories(self, client, sample_major):
        resp = client.get("/api/majors/categories")
        data = resp.json()
        assert data["success"] is True
        assert "工学" in data["data"]
