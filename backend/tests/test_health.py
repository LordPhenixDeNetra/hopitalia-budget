from fastapi.testclient import TestClient

from hopitalia_budget.main import app


def test_health_repond_ok() -> None:
    reponse = TestClient(app).get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok"}
