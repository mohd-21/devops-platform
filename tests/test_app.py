import pytest

from app.main import create_app


@pytest.fixture()
def client():
    return create_app().test_client()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_version(client):
    body = client.get("/version").get_json()
    assert "version" in body and "environment" in body


def test_create_and_list_deployment(client):
    payload = {"service": "checkout", "version": "1.4.0", "status": "success"}
    created = client.post("/api/deployments", json=payload)
    assert created.status_code == 201
    assert created.get_json()["id"] == 1

    listed = client.get("/api/deployments").get_json()
    assert len(listed) == 1
    assert listed[0]["service"] == "checkout"


def test_filter_by_service(client):
    client.post("/api/deployments", json={"service": "a", "version": "1", "status": "success"})
    client.post("/api/deployments", json={"service": "b", "version": "1", "status": "failed"})
    only_b = client.get("/api/deployments?service=b").get_json()
    assert [d["service"] for d in only_b] == ["b"]


def test_validation_missing_fields(client):
    res = client.post("/api/deployments", json={"service": "x"})
    assert res.status_code == 400
    assert "missing fields" in res.get_json()["error"]


def test_validation_bad_status(client):
    res = client.post(
        "/api/deployments", json={"service": "x", "version": "1", "status": "weird"}
    )
    assert res.status_code == 400


def test_metrics_exposed(client):
    client.get("/health")
    res = client.get("/metrics")
    assert res.status_code == 200
    assert b"http_requests_total" in res.data
