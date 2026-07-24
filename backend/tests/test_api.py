from backend.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_status_uses_snapshot_without_database() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_company_pagination_and_validation() -> None:
    response = client.get("/api/v1/companies?page=1&page_size=10")
    assert response.status_code == 200
    assert response.json()["total"] >= 50
    assert len(response.json()["items"]) == 10
    assert client.get("/api/v1/companies?page=0").status_code == 422


def test_search_returns_real_record() -> None:
    response = client.get("/api/v1/search", params={"q": "OpenAI"})
    assert response.status_code == 200
    assert any(item.get("name") == "OpenAI" for item in response.json()["items"])


def test_internal_sync_requires_secret() -> None:
    response = client.post("/api/internal/sync/run", json={})
    assert response.status_code in {401, 503}
