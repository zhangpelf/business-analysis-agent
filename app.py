"""Streamlit demonstration interface for the Business Analysis Agent."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from business_analysis_agent.core import DataValidationError, analyze_dataframe, load_demo_data
from business_analysis_agent.llm_summary import (
    LLMNotConfiguredError,
    UnsafeSummaryError,
    is_llm_configured,
    summarize_evidence,
)


st.set_page_config(page_title="经营分析 Agent", page_icon="📈", layout="wide")
st.title("经营分析 Agent")
st.caption("公开/合成数据演示 · 确定性诊断 · 可追溯证据 · 非投资建议")

with st.expander("数据边界与使用说明", expanded=True):
    st.markdown(
        "本作品只包含合成示例数据。上传前请删除客户、订单、个人信息和任何受保密义务约束的数据。"
        "系统按上传数据计算，不识别因果关系；建议须由业务负责人结合季节性和外部事件复核。"
    )

sample = load_demo_data()
st.download_button(
    "下载 CSV 模板（合成示例）",
    sample.to_csv(index=False).encode("utf-8-sig"),
    file_name="business_metrics_template.csv",
    mime="text/csv",
)

uploaded_file = st.file_uploader("上传经营数据 CSV", type=["csv"])
use_demo = st.toggle("使用内置合成示例", value=uploaded_file is None)

if use_demo:
    source_data = sample
    source_label = "内置合成示例"
elif uploaded_file is not None:
    try:
        source_data = pd.read_csv(uploaded_file)
        source_label = f"用户上传：{uploaded_file.name}"
    except Exception as exc:
        st.error(f"无法读取 CSV：{exc}")
        st.stop()
else:
    st.info("上传 CSV，或开启内置合成示例。")
    st.stop()

st.caption(f"当前数据来源：{source_label}")
with st.expander("输入数据预览"):
    st.dataframe(source_data, use_container_width=True, hide_index=True)

if st.button("运行确定性诊断", type="primary"):
    try:
        with st.spinner("依次完成校验、KPI 计算、异常识别、驱动归因和报告生成…"):
            result = analyze_dataframe(source_data)
    except DataValidationError as exc:
        st.error(str(exc))
        st.stop()

    st.session_state["analysis_result"] = result

result = st.session_state.get("analysis_result")
if result:
    st.subheader("期间 KPI")
    kpi_frame = pd.DataFrame(result["metrics"])[
        [
            "period",
            "sessions",
            "orders",
            "revenue",
            "conversion_rate",
            "aov",
            "contribution_margin",
            "contribution_margin_rate",
        ]
    ]
    st.dataframe(kpi_frame, use_container_width=True, hide_index=True)

    st.subheader("预警")
    if result["anomalies"]:
        st.dataframe(pd.DataFrame(result["anomalies"]), use_container_width=True, hide_index=True)
    else:
        st.success("未发现超过当前阈值的异常。")

    st.subheader("可追溯证据")
    st.dataframe(pd.DataFrame(result["evidence"]), use_container_width=True, hide_index=True)

    st.subheader("建议与复核边界")
    for item in result["recommendations"]:
        st.markdown(f"- **{item['period']}**：{item['action']}  ")
        st.caption(f"触发证据：{item['trigger']}\n\n{item['boundary']}")

    st.subheader("可选 LLM 文字摘要")
    if is_llm_configured():
        st.caption("仅发送当前页面的确定性证据、预警和建议；模型不能输出数字，违规结果会被拒绝。")
        if st.button("生成受约束的文字摘要"):
            try:
                st.session_state["llm_summary"] = summarize_evidence(result)
            except (LLMNotConfiguredError, UnsafeSummaryError) as exc:
                st.warning(str(exc))
            except Exception as exc:
                st.error(f"摘要调用失败，未影响确定性报告：{exc}")
        if summary := st.session_state.get("llm_summary"):
            st.info(summary)
    else:
        st.caption("未配置 LLM；当前版本仍可完整运行确定性分析。配置项见 `.env.example`。")

    st.download_button(
        "下载 Markdown 报告",
        result["report_markdown"].encode("utf-8"),
        file_name="business-analysis-report.md",
        mime="text/markdown",
    )
