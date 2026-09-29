from fastapi.testclient import TestClient

from datatalk.main import app


def test_openapi_describes_main_resource_responses():
    paths = app.openapi()["paths"]
    for method, path in (
        ("get", "/api/session"),
        ("get", "/api/catalog"),
        ("get", "/api/analyses/{analysis_id}"),
        ("get", "/api/reports/{report_id}"),
        ("post", "/api/imports/preview"),
        ("post", "/api/imports/publish"),
    ):
        responses = paths[path][method]["responses"]
        success = responses.get("200") or responses.get("201")
        assert success["content"]["application/json"]["schema"]


def test_cross_site_writes_are_denied_before_authentication():
    with TestClient(app) as client:
        response = client.post("/api/auth/logout", headers={"Origin": "https://other.example"})
        assert response.status_code == 403
        response = client.post("/api/auth/logout", headers={"Sec-Fetch-Site": "cross-site"})
        assert response.status_code == 403
