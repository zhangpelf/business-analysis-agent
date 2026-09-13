"""LangGraph orchestration for the deterministic business-diagnosis pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

import pandas as pd

try:  # Keep the package testable in a minimal local Python environment.
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - exercised only without installed deps
    END = None
    StateGraph = None

from .core import (
    calculate_metrics,
    detect_anomalies,
    diagnose_drivers,
    generate_recommendations,
    render_report,
    validate_dataframe,
)


class AnalysisState(TypedDict, total=False):
    raw_data: pd.DataFrame
    validated_data: pd.DataFrame
    metrics: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    recommendations: list[dict[str, str]]
    report_markdown: str


def validate_data(state: AnalysisState) -> dict[str, Any]:
    return {"validated_data": validate_dataframe(state["raw_data"])}


def calculate_metrics_node(state: AnalysisState) -> dict[str, Any]:
    return {"metrics": calculate_metrics(state["validated_data"])}


def detect_anomalies_node(state: AnalysisState) -> dict[str, Any]:
    return {"anomalies": detect_anomalies(state["metrics"])}


def diagnose_drivers_node(state: AnalysisState) -> dict[str, Any]:
    return {"evidence": diagnose_drivers(state["metrics"])}


def generate_recommendations_node(state: AnalysisState) -> dict[str, Any]:
    return {"recommendations": generate_recommendations(state["evidence"])}


def render_report_node(state: AnalysisState) -> dict[str, Any]:
    return {
        "report_markdown": render_report(
            state["metrics"],
            state["anomalies"],
            state["evidence"],
            state["recommendations"],
        )
    }


class _DeterministicWorkflowFallback:
    """Same ordered contract for offline tests before LangGraph is installed.

    The production dependency remains LangGraph. This fallback intentionally does
    not add branching or agent autonomy; it merely preserves the six explicit
    stages so the public deterministic core can be verified with a minimal env.
    """

    _nodes = (
        validate_data,
        calculate_metrics_node,
        detect_anomalies_node,
        diagnose_drivers_node,
        generate_recommendations_node,
        render_report_node,
    )

    def invoke(self, initial_state: AnalysisState) -> AnalysisState:
        state = dict(initial_state)
        for node in self._nodes:
            state.update(node(state))
        return state


def create_workflow():
    """Create the explicit, six-stage analysis graph used by UI and API."""
    if StateGraph is None:
        return _DeterministicWorkflowFallback()

    graph = StateGraph(AnalysisState)
    graph.add_node("validate_data", validate_data)
    graph.add_node("calculate_metrics", calculate_metrics_node)
    graph.add_node("detect_anomalies", detect_anomalies_node)
    graph.add_node("diagnose_drivers", diagnose_drivers_node)
    graph.add_node("generate_recommendations", generate_recommendations_node)
    graph.add_node("render_report", render_report_node)
    graph.set_entry_point("validate_data")
    graph.add_edge("validate_data", "calculate_metrics")
    graph.add_edge("calculate_metrics", "detect_anomalies")
    graph.add_edge("detect_anomalies", "diagnose_drivers")
    graph.add_edge("diagnose_drivers", "generate_recommendations")
    graph.add_edge("generate_recommendations", "render_report")
    graph.add_edge("render_report", END)
    return graph.compile()
