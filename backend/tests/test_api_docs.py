def test_openapi_spec_is_served(client):
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.json["openapi"] == "3.0.3"
    assert "/api/v1/health" in response.json["paths"]


def test_swagger_ui_uses_openapi_spec(client):
    response = client.get("/api/docs")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    assert b'SwaggerUIBundle' in response.data
    assert b'url: "/api/openapi.json"' in response.data