# Business Analysis Agent / 经营分析 Agent

一个面向经营分析场景的公开作品集项目。它将 **CSV 数据校验 → KPI 计算 → 异常识别 → 收入驱动归因 → 受证据约束的建议 → Markdown 报告** 编排为一个可复现的 LangGraph 工作流。

它复用了现有行业研究项目的工程思想（工作流、可视化、Docker、测试），但不复制任何投研材料、内部数据或客户资料。

## 为什么做它

我希望把金融/产业研究与实际经营分析经历中积累的问题，转化为一个可公开演示的 AI 应用工程作品：

- 不把大模型当计算器；核心 KPI、归因和预警均由确定性代码完成；
- 每条建议关联到结构化证据，避免“看似合理但没有数据来源”的生成结论；
- 不依赖 API Key，离线也能复现完整的诊断闭环；
- 仅使用内置合成数据或用户主动上传的已脱敏公开数据。

## 工作流

```text
validate_data
  -> calculate_metrics
  -> detect_anomalies
  -> diagnose_drivers
  -> generate_recommendations
  -> render_report
```

收入使用 `sessions × conversion_rate × AOV` 进行顺序分解；贡献毛利为：

```text
revenue - variable_cost - marketing_cost
```

## 输入数据契约

CSV 必须包含下列列，金额和数量必须非负，且 `orders <= sessions`。每个 `period`
汇总后的 `sessions`、`orders` 与 `revenue` 必须均大于零；无经营活动的期间应移除或另行处理，
以避免转化率或客单价没有定义：

| 列 | 含义 |
|---|---|
| `period` | 可解析日期，如 `2026-01-01` |
| `channel` | 渠道名称 |
| `sessions` | 会话/访问量 |
| `orders` | 订单量 |
| `revenue` | 收入 |
| `variable_cost` | 变动成本 |
| `marketing_cost` | 营销投放成本 |

内置的 `demo_metrics.csv` 是合成数据，特意包含可识别的收入和毛利恶化情形。

每条会话量、转化率、客单价证据还提供结构化字段 `revenue_impact`。同一期间这三项
`revenue_impact` 之和应精确等于该期间相对于上一期的收入变化，便于独立复算。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Streamlit 界面
streamlit run app.py --server.address 127.0.0.1

# FastAPI 服务
uvicorn business_analysis_agent.api:app --host 127.0.0.1 --reload

# 测试
pytest
```

Docker 演示界面：

```bash
docker build -t business-analysis-agent .
docker run --rm -p 127.0.0.1:8501:8501 business-analysis-agent
```

API 示例：

```bash
curl http://127.0.0.1:8000/health
```

`POST /analyze` 接收形如 `{ "rows": [ ... ] }` 的 JSON，返回 KPI、异常、证据、建议和 Markdown 报告。

安装项目依赖后，工作流由 LangGraph 执行。为了让纯确定性计算在最小本地环境中也能测试，未安装 LangGraph 时会使用同样六个节点顺序的轻量回退执行器；它不改变结果，也不增加任何模型调用。

## 数据、安全与结论边界

- 不提交 `.env`、密钥、订单明细、客户资料、未公开业务指标或尽调材料。
- 上传前必须完成脱敏并确认拥有使用权；默认演示只使用合成数据。
- 该工具做的是描述性/诊断性分析，不证明因果关系；应由业务负责人核对季节性、口径变化和外部事件。
- 不构成投资、定价、预算或经营决策建议。
- 默认不调用 LLM。若显式配置 `.env.example` 中的 OpenAI-compatible 参数，界面可请求一个可选文字摘要；它只能接收本工作流的异常、证据和建议，且任何带数字的模型输出都会被拒绝展示。确定性报告始终是唯一数值来源。

## 当前限制与下一步

当前的预警阈值为透明的规则（收入环比下降 ≥10%、贡献毛利率下降 ≥5 个百分点）。下一步可加入：渠道级贡献拆解、用户确认的业务阈值、基于标注案例的评估集、异步任务/日志、权限与审计记录。它们应在有真实但可公开的需求与数据口径后再加入，而不是为了堆栈而加入。
