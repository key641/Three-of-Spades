from fastapi.testclient import TestClient

from app.main import app


def test_development_cors_accepts_localhost_on_dynamic_port() -> None:
    response = TestClient(app).options(
        "/api/evaluation/run",
        headers={
            "Origin": "http://localhost:5176",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5176"


def test_development_cors_accepts_private_network_origin() -> None:
    response = TestClient(app).options(
        "/api/evaluation/run",
        headers={
            "Origin": "http://172.20.10.3:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://172.20.10.3:5173"
