from business_analysis_agent.core import load_demo_data
from business_analysis_agent.workflow import create_workflow


def test_workflow_runs_without_network_or_llm():
    result = create_workflow().invoke({"raw_data": load_demo_data()})
    assert len(result["metrics"]) == 3
    assert result["anomalies"]
    assert result["evidence"]
    assert result["recommendations"]
    assert "经营分析 Agent 报告" in result["report_markdown"]
