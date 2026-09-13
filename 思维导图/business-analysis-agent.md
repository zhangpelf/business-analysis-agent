# 经营分析 Agent · Business Analysis Agent

## 定位
- 公开作品集项目：面向经营分析场景的 AI 应用工程
- 编排链路：CSV 数据校验 → KPI 计算 → 异常识别 → 收入驱动归因 → 证据约束建议 → Markdown 报告
- 核心原则
  - 不把大模型当计算器：核心 KPI、归因、预警均由确定性代码完成
  - 每条建议关联结构化证据，拒绝"看似合理但无数据来源"的结论
  - 不依赖 API Key，离线可复现完整诊断闭环
  - 仅使用内置合成数据或用户主动上传的已脱敏公开数据

## 六节点工作流（LangGraph）
- validate_data · 数据校验
- calculate_metrics · KPI 计算
- detect_anomalies · 异常识别
- diagnose_drivers · 收入驱动归因
- generate_recommendations · 证据约束建议
- render_report · Markdown 报告
- 轻量回退执行器：未装 LangGraph 时用同顺序确定性执行，结果不变、无模型调用

## 核心计算口径
- 收入顺序分解：收入 = sessions × conversion_rate × AOV
- 贡献毛利 = revenue − variable_cost − marketing_cost
- 证据可复算：同期间 会话/转化率/客单价 的 revenue_impact 之和 = 相对上期收入变化
- 预警规则（透明阈值）
  - 收入环比下降 ≥ 10%
  - 贡献毛利率下降 ≥ 5 个百分点

## 输入数据契约（CSV 7 列）
- period · 可解析日期
- channel · 渠道名称
- sessions · 会话/访问量
- orders · 订单量
- revenue · 收入
- variable_cost · 变动成本
- marketing_cost · 营销投放成本
- 约束
  - 金额与数量非负，orders ≤ sessions
  - 每 period 汇总后 sessions/orders/revenue 均 > 0
  - 内置 demo_metrics.csv 合成数据，含可识别的收入和毛利恶化情形

## 技术栈
- Python ≥ 3.11
- langgraph · 工作流编排
- pandas · 确定性计算
- fastapi + uvicorn · API 服务
- streamlit · 交互界面
- docker · 容器化演示
- pytest · 测试（4 个测试模块）

## 代码结构
- business_analysis_agent/core.py · 确定性核心
  - validate_dataframe 数据校验
  - calculate_metrics KPI 计算
  - detect_anomalies 异常识别
  - diagnose_drivers 收入驱动归因
  - generate_recommendations 证据约束建议
  - render_report Markdown 报告
  - analyze_dataframe 端到端入口
- business_analysis_agent/workflow.py · LangGraph 编排（AnalysisState + 6 节点 + 回退执行器）
- business_analysis_agent/api.py · FastAPI 接口
  - GET /health 健康检查
  - POST /analyze 接收 {rows:[...]}，返回 KPI/异常/证据/建议/报告
- business_analysis_agent/llm_summary.py · 可选 LLM 摘要
  - 仅接收本工作流异常/证据/建议
  - 含数字的模型输出被拒绝展示
- app.py · Streamlit 界面（上传/演示数据 + 下载报告）
- tests/ · test_core / test_workflow / test_api / test_llm_summary
- audit/ · 审计文档（计算契约 / 校验清单 / 验证记录）

## 运行方式
- Streamlit 界面：streamlit run app.py --server.address 127.0.0.1
- FastAPI 服务：uvicorn business_analysis_agent.api:app --reload
- Docker：docker build -t business-analysis-agent . && docker run -p 127.0.0.1:8501:8501
- 测试：pytest
- API 示例：curl http://127.0.0.1:8000/health

## 数据、安全与结论边界
- 不提交 .env、密钥、订单明细、客户资料、未公开业务指标、尽调材料
- 上传前必须脱敏并确认拥有使用权；默认演示只用合成数据
- 描述性/诊断性分析，不证明因果关系，需业务负责人核对季节性/口径/外部事件
- 不构成投资、定价、预算或经营决策建议
- 确定性报告始终是唯一数值来源；LLM 输出仅作可选文字摘要

## 当前限制与下一步
- 当前限制
  - 预警阈值为固定透明规则
  - 仅收入驱动归因，未做渠道级贡献拆解
- 下一步
  - 渠道级贡献拆解
  - 用户确认的业务阈值
  - 基于标注案例的评估集
  - 异步任务 / 日志
  - 权限与审计记录
