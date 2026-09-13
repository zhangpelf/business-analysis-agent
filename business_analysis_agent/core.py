"""Deterministic business-analysis primitives.

The module deliberately separates arithmetic and diagnosis from language-model
generation. Every recommendation is traceable to a structured evidence record,
which keeps the demo safe to run without an external model or private data.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = (
    "period",
    "channel",
    "sessions",
    "orders",
    "revenue",
    "variable_cost",
    "marketing_cost",
)
NUMERIC_COLUMNS = REQUIRED_COLUMNS[2:]


class DataValidationError(ValueError):
    """Raised when an uploaded operational data set is not safe to analyze."""


@dataclass(frozen=True)
class Evidence:
    """A traceable diagnostic fact used by the report and recommendations."""

    period: str
    metric: str
    current: float
    baseline: float
    delta: float
    delta_pct: float | None
    explanation: str
    severity: str = "info"
    revenue_impact: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "metric": self.metric,
            "current": round(self.current, 4),
            "baseline": round(self.baseline, 4),
            "delta": round(self.delta, 4),
            "delta_pct": None if self.delta_pct is None else round(self.delta_pct, 2),
            "explanation": self.explanation,
            "severity": self.severity,
            "revenue_impact": (
                None if self.revenue_impact is None else round(self.revenue_impact, 4)
            ),
        }


def load_demo_data() -> pd.DataFrame:
    """Load the deliberately diagnosable, synthetic demonstration data."""
    demo_path = files("business_analysis_agent").joinpath("data/demo_metrics.csv")
    return pd.read_csv(demo_path)


def validate_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Return normalized data or a clear validation error for the upload."""
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise DataValidationError(
            "缺少必填列：" + "、".join(missing) + "。请使用模板中的标准列名。"
        )
    if data.empty:
        raise DataValidationError("上传的数据为空。请至少提供一个 period × channel 观测值。")

    normalized = data.loc[:, REQUIRED_COLUMNS].copy()
    normalized["period"] = pd.to_datetime(normalized["period"], errors="coerce")
    if normalized["period"].isna().any():
        raise DataValidationError("period 必须是可解析日期，例如 2026-01-01。")

    normalized["channel"] = normalized["channel"].astype("string").str.strip()
    if normalized["channel"].isna().any() or (normalized["channel"] == "").any():
        raise DataValidationError("channel 不能为空，例如 Direct、Paid 或 Store。")

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if normalized[column].isna().any():
            raise DataValidationError(f"{column} 必须为数值，不能包含空值或文本。")
        if (normalized[column] < 0).any():
            raise DataValidationError(f"{column} 不能为负数。")

    if (normalized["orders"] > normalized["sessions"]).any():
        raise DataValidationError("orders 不能大于 sessions；请检查口径或单位。")

    period_totals = normalized.groupby("period", as_index=False)[
        ["sessions", "orders", "revenue"]
    ].sum()
    undefined_funnel_periods = period_totals.loc[
        (period_totals["sessions"] <= 0)
        | (period_totals["orders"] <= 0)
        | (period_totals["revenue"] <= 0),
        "period",
    ]
    if not undefined_funnel_periods.empty:
        periods = "、".join(
            pd.Timestamp(value).date().isoformat() for value in undefined_funnel_periods
        )
        raise DataValidationError(
            "每个 period 汇总后的 sessions、orders 和 revenue 必须均大于 0，"
            "否则转化率或客单价无法定义；请移除无经营活动期间或另行处理。"
            f"问题期间：{periods}。"
        )

    return normalized.sort_values(["period", "channel"], ignore_index=True)


def _pct_change(current: float, baseline: float) -> float | None:
    if baseline == 0:
        return None
    return (current / baseline - 1) * 100


def calculate_metrics(data: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate channel observations into period-level, auditable KPIs."""
    grouped = (
        data.groupby("period", as_index=False)[list(NUMERIC_COLUMNS)]
        .sum()
        .sort_values("period", ignore_index=True)
    )
    grouped["conversion_rate"] = grouped["orders"] / grouped["sessions"].where(
        grouped["sessions"] != 0
    )
    grouped["aov"] = grouped["revenue"] / grouped["orders"].where(
        grouped["orders"] != 0
    )
    grouped["contribution_margin"] = (
        grouped["revenue"] - grouped["variable_cost"] - grouped["marketing_cost"]
    )
    grouped["contribution_margin_rate"] = grouped["contribution_margin"] / grouped[
        "revenue"
    ].where(grouped["revenue"] != 0)

    tracked = (
        "sessions",
        "orders",
        "revenue",
        "conversion_rate",
        "aov",
        "contribution_margin",
        "contribution_margin_rate",
    )
    for metric in tracked:
        grouped[f"{metric}_delta"] = grouped[metric].diff()
        grouped[f"{metric}_pct_change"] = grouped[metric].pct_change() * 100

    records: list[dict[str, Any]] = []
    for row in grouped.to_dict(orient="records"):
        row["period"] = pd.Timestamp(row["period"]).date().isoformat()
        for key, value in row.items():
            if key != "period" and pd.isna(value):
                row[key] = None
        records.append(row)
    return records


def detect_anomalies(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag material revenue and margin deterioration using transparent rules."""
    anomalies: list[dict[str, Any]] = []
    for current in metrics[1:]:
        revenue_change = current["revenue_pct_change"]
        margin_rate_delta = current["contribution_margin_rate_delta"]
        if revenue_change is not None and revenue_change <= -10:
            anomalies.append(
                {
                    "period": current["period"],
                    "type": "revenue_decline",
                    "severity": "high" if revenue_change <= -20 else "medium",
                    "message": f"收入环比下降 {abs(revenue_change):.1f}%，超过 10% 预警阈值。",
                }
            )
        if margin_rate_delta is not None and margin_rate_delta <= -0.05:
            anomalies.append(
                {
                    "period": current["period"],
                    "type": "margin_rate_decline",
                    "severity": "high" if margin_rate_delta <= -0.10 else "medium",
                    "message": (
                        "贡献毛利率环比下降 "
                        f"{abs(margin_rate_delta) * 100:.1f} 个百分点，需检查成本或投放效率。"
                    ),
                }
            )
    return anomalies


def diagnose_drivers(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create evidence from an exact sequential revenue-driver decomposition."""
    evidence: list[Evidence] = []
    labels = {"sessions": "会话量", "conversion_rate": "转化率", "aov": "客单价"}
    for baseline, current in zip(metrics, metrics[1:]):
        session_effect = (current["sessions"] - baseline["sessions"]) * baseline[
            "conversion_rate"
        ] * baseline["aov"]
        conversion_effect = current["sessions"] * (
            current["conversion_rate"] - baseline["conversion_rate"]
        ) * baseline["aov"]
        aov_effect = current["sessions"] * current["conversion_rate"] * (
            current["aov"] - baseline["aov"]
        )
        effects = {
            "sessions": session_effect,
            "conversion_rate": conversion_effect,
            "aov": aov_effect,
        }
        total_change = current["revenue"] - baseline["revenue"]
        for key, effect in effects.items():
            if abs(effect) < 0.01:
                continue
            current_value = current[key]
            baseline_value = baseline[key]
            delta = current_value - baseline_value
            evidence.append(
                Evidence(
                    period=current["period"],
                    metric=labels[key],
                    current=current_value,
                    baseline=baseline_value,
                    delta=delta,
                    delta_pct=_pct_change(current_value, baseline_value),
                    explanation=(
                        f"{labels[key]}变化估计带来收入 {'增加' if effect >= 0 else '减少'} "
                        f"{abs(effect):,.0f}；本期总收入变化为 {total_change:,.0f}。"
                    ),
                    severity="high" if effect < 0 and abs(effect) >= abs(total_change) * 0.4 else "info",
                    revenue_impact=effect,
                )
            )

        margin_delta = current["contribution_margin"] - baseline["contribution_margin"]
        evidence.append(
            Evidence(
                period=current["period"],
                metric="贡献毛利",
                current=current["contribution_margin"],
                baseline=baseline["contribution_margin"],
                delta=margin_delta,
                delta_pct=_pct_change(
                    current["contribution_margin"], baseline["contribution_margin"]
                ),
                explanation=(
                    "贡献毛利变化已同时计入收入、变动成本与营销成本；"
                    f"贡献毛利率为 {current['contribution_margin_rate'] * 100:.1f}%。"
                ),
                severity="high" if margin_delta < 0 else "info",
            )
        )
    return [item.as_dict() for item in evidence]


def generate_recommendations(evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Turn deterministic evidence into bounded, non-investment recommendations."""
    recommendations: list[dict[str, str]] = []
    for item in evidence:
        if item["delta"] >= 0:
            continue
        if item["metric"] == "会话量":
            action = "按渠道拆分新增与自然流量，先核对预算、投放节奏和渠道可用性，再暂停低效增量。"
        elif item["metric"] == "转化率":
            action = "按漏斗环节检查落地页、库存、价格和支付失败率；对一个关键假设进行小流量 A/B 验证。"
        elif item["metric"] == "客单价":
            action = "检查商品/订单结构与折扣深度，评估组合购、门槛与价格带调整对毛利的影响。"
        elif item["metric"] == "贡献毛利":
            action = "将营销成本与变动成本按渠道归因，优先压缩毛利为负或边际贡献持续恶化的活动。"
        else:
            continue
        recommendations.append(
            {
                "period": item["period"],
                "trigger": item["explanation"],
                "action": action,
                "boundary": "建议仅基于上传数据；执行前应由业务负责人核验口径、季节性和外部事件。",
            }
        )
    return recommendations or [
        {
            "period": "all",
            "trigger": "未发现超过当前规则阈值的负向变化。",
            "action": "保持监控，并在新增活动或渠道变化后重新运行分析。",
            "boundary": "结果仅反映上传数据，不构成经营或投资决策结论。",
        }
    ]


def render_report(
    metrics: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    recommendations: list[dict[str, str]],
) -> str:
    """Render a portable Markdown report with visible data and decision boundaries."""
    lines = [
        "# 经营分析 Agent 报告",
        "",
        "> 数据来源：用户上传的 CSV 或内置合成示例数据。该报告不使用任何内部、客户或投资数据，也不构成投资建议。",
        "",
        "## 期间 KPI",
        "",
        "| 期间 | 收入 | 转化率 | 客单价 | 贡献毛利 | 贡献毛利率 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for metric in metrics:
        lines.append(
            "| {period} | {revenue:,.0f} | {conversion_rate:.2%} | {aov:,.2f} | "
            "{contribution_margin:,.0f} | {contribution_margin_rate:.2%} |".format(
                **metric
            )
        )
    lines.extend(["", "## 预警", ""])
    lines.extend(
        [f"- **{item['period']}** · {item['message']}" for item in anomalies]
        or ["- 未发现超过当前预警阈值的异常。"]
    )
    lines.extend(["", "## 可追溯证据", ""])
    for item in evidence:
        change = "n/a" if item["delta_pct"] is None else f"{item['delta_pct']:.1f}%"
        lines.append(
            f"- **{item['period']} · {item['metric']}**：{item['explanation']} "
            f"（变化：{change}）"
        )
    lines.extend(["", "## 建议与复核边界", ""])
    for item in recommendations:
        lines.append(f"- **{item['period']}**：{item['action']}  {item['boundary']}")
    return "\n".join(lines) + "\n"


def analyze_dataframe(data: pd.DataFrame) -> dict[str, Any]:
    """Run the public deterministic workflow and return a JSON-friendly result."""
    from .workflow import create_workflow

    return create_workflow().invoke({"raw_data": data})
