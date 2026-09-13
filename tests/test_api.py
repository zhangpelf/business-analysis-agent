from fastapi.testclient import TestClient

from business_analysis_agent.api import app
from business_analysis_agent.core import load_demo_data


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analyze_endpoint_runs_without_llm():
    response = client.post("/analyze", json={"rows": load_demo_data().to_dict("records")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["metrics"]) == 3
    assert body["evidence"]
    assert "经营分析 Agent 报告" in body["report_markdown"]


def test_analyze_endpoint_returns_actionable_validation_error():
    response = client.post("/analyze", json={"rows": [{"period": "2026-01-01"}]})
    assert response.status_code == 422
    assert "缺少必填列" in response.json()["detail"]
