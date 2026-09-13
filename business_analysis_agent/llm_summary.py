"""Fail-closed optional LLM narration for already-computed evidence.

The deterministic workflow remains the source of truth. This adapter is opt-in:
without an environment configuration it does nothing, and with one it may only
produce a qualitative summary of the supplied evidence. Numeric output is
rejected so it cannot introduce a new metric or change a calculated value.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


class LLMNotConfiguredError(RuntimeError):
    """Raised when an optional summary is requested without explicit settings."""


class UnsafeSummaryError(ValueError):
    """Raised when an LLM response violates the no-new-numbers contract."""


_NUMERIC_PATTERN = re.compile(r"\d|[零一二三四五六七八九十百千万亿]", re.UNICODE)


def is_llm_configured() -> bool:
    """Return true only when all required OpenAI-compatible settings exist."""
    return all(
        os.getenv(name, "").strip()
        for name in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")
    )


def build_summary_messages(result: dict[str, Any]) -> list[dict[str, str]]:
    """Create a narrow prompt containing only deterministic result fields."""
    evidence_bundle = {
        "anomalies": result.get("anomalies", []),
        "evidence": result.get("evidence", []),
        "recommendations": result.get("recommendations", []),
    }
    source_json = json.dumps(evidence_bundle, ensure_ascii=False, sort_keys=True)
    return [
        {
            "role": "system",
            "content": (
                "你是经营分析报告的文字编辑。只能基于用户消息中的 JSON 证据做三条中文定性摘要。"
                "不得新增事实、因果、主体、指标或建议；不得输出任何阿拉伯数字或中文数字。"
                "具体数值已在界面证据表中展示，因此用‘证据显示’等定性表述即可。"
                "若证据不足，明确写‘需要业务复核’。"
            ),
        },
        {"role": "user", "content": source_json},
    ]


def validate_summary(summary: str) -> str:
    """Reject any numeric response rather than risking an invented metric."""
    normalized = summary.strip()
    if not normalized:
        raise UnsafeSummaryError("LLM 摘要为空，已拒绝展示。")
    if _NUMERIC_PATTERN.search(normalized):
        raise UnsafeSummaryError("LLM 摘要包含数字，无法证明其来自既有证据，已拒绝展示。")
    return normalized


def summarize_evidence(result: dict[str, Any], timeout: float = 30.0) -> str:
    """Request a qualitative, fail-closed OpenAI-compatible evidence summary."""
    if not is_llm_configured():
        raise LLMNotConfiguredError(
            "未配置 OPENAI_BASE_URL、OPENAI_API_KEY 和 OPENAI_MODEL；确定性报告仍可正常使用。"
        )
    base_url = os.environ["OPENAI_BASE_URL"].rstrip("/")
    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": os.environ["OPENAI_MODEL"],
            "messages": build_summary_messages(result),
            "temperature": 0,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise UnsafeSummaryError("LLM 返回格式无效，已拒绝展示。") from exc
    return validate_summary(content)
