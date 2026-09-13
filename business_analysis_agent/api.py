"""FastAPI surface for programmatic, deterministic business diagnosis."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .core import DataValidationError, analyze_dataframe


class AnalyzeRequest(BaseModel):
    """Rows follow the public CSV schema documented in the README."""

    rows: list[dict[str, Any]] = Field(min_length=1)


class AnalyzeResponse(BaseModel):
    metrics: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    recommendations: list[dict[str, str]]
    report_markdown: str


app = FastAPI(
    title="Business Analysis Agent API",
    version="0.1.0",
    description=(
        "Public/synthetic-data business diagnosis API. It is deterministic, "
        "does not require an LLM, and is not investment advice."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "deterministic-public-data"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = analyze_dataframe(pd.DataFrame(request.rows))
    except DataValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnalyzeResponse(
        metrics=result["metrics"],
        anomalies=result["anomalies"],
        evidence=result["evidence"],
        recommendations=result["recommendations"],
        report_markdown=result["report_markdown"],
    )
