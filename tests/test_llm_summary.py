import pytest

from business_analysis_agent.llm_summary import (
    UnsafeSummaryError,
    build_summary_messages,
    validate_summary,
)


def test_summary_prompt_only_receives_evidence_fields():
    result = {
        "raw_data": "must not be serialized",
        "metrics": [{"revenue": 100}],
        "anomalies": [{"type": "revenue_decline"}],
        "evidence": [{"metric": "会话量", "delta": -1}],
        "recommendations": [{"action": "复核渠道"}],
    }
    messages = build_summary_messages(result)
    assert "must not be serialized" not in messages[1]["content"]
    assert "revenue_decline" in messages[1]["content"]
    assert "会话量" in messages[1]["content"]


def test_summary_rejects_numbers_to_prevent_metric_invention():
    with pytest.raises(UnsafeSummaryError, match="包含数字"):
        validate_summary("收入下降了百分之十")


def test_summary_accepts_qualitative_text_only():
    assert validate_summary("证据显示转化环节需要业务复核。") == "证据显示转化环节需要业务复核。"
