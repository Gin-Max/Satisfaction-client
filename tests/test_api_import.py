from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_home_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "status" in response.json()
