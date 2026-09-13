from __future__ import annotations

import pandas as pd
import pytest

from business_analysis_agent.core import (
    DataValidationError,
    calculate_metrics,
    detect_anomalies,
    diagnose_drivers,
    load_demo_data,
    validate_dataframe,
)


def test_validation_rejects_missing_required_column():
    data = load_demo_data().drop(columns=["marketing_cost"])
    with pytest.raises(DataValidationError, match="marketing_cost"):
        validate_dataframe(data)


def test_validation_rejects_orders_greater_than_sessions():
    data = load_demo_data()
    data.loc[0, "orders"] = data.loc[0, "sessions"] + 1
    with pytest.raises(DataValidationError, match="orders"):
        validate_dataframe(data)


def test_validation_rejects_period_with_undefined_funnel_denominators():
    data = load_demo_data()
    data.loc[data["period"] == "2026-02-01", ["orders", "revenue"]] = 0
    with pytest.raises(DataValidationError, match="每个 period 汇总后的 sessions、orders 和 revenue"):
        validate_dataframe(data)


def test_metrics_are_deterministic_and_auditable():
    metrics = calculate_metrics(validate_dataframe(load_demo_data()))
    january = metrics[0]
    assert january["revenue"] == 112000
    assert january["conversion_rate"] == pytest.approx(0.056)
    assert january["aov"] == pytest.approx(100)
    assert january["contribution_margin"] == 52800


def test_demo_data_has_revenue_and_margin_warnings():
    metrics = calculate_metrics(validate_dataframe(load_demo_data()))
    anomalies = detect_anomalies(metrics)
    assert {item["type"] for item in anomalies} >= {
        "revenue_decline",
        "margin_rate_decline",
    }


def test_driver_diagnosis_is_traceable():
    metrics = calculate_metrics(validate_dataframe(load_demo_data()))
    evidence = diagnose_drivers(metrics)
    assert any(item["metric"] == "会话量" for item in evidence)
    assert any(item["metric"] == "转化率" for item in evidence)
    assert all({"metric", "current", "baseline", "delta", "explanation"} <= set(item) for item in evidence)


def test_driver_impacts_reconcile_to_each_period_revenue_change():
    metrics = calculate_metrics(validate_dataframe(load_demo_data()))
    evidence = diagnose_drivers(metrics)

    for baseline, current in zip(metrics, metrics[1:]):
        impacts = [
            item["revenue_impact"]
            for item in evidence
            if item["period"] == current["period"]
            and item["revenue_impact"] is not None
        ]
        assert sum(impacts) == pytest.approx(current["revenue"] - baseline["revenue"])
