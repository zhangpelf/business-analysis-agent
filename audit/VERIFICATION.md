# 验证记录

本文件在每次生成审计归档时更新，记录命令、结果和未覆盖项。完整性校验见归档根目录的 `SHA256SUMS`。

## 预期命令

```bash
python3 -m pytest -q
python3 -m compileall -q app.py business_analysis_agent tests
python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir /private/tmp/business-analysis-agent-wheel .
```

## 本次归档结果（2026-07-31）

| 检查 | 结果 | 说明 |
|---|---|---|
| Python 环境 | 通过 | `Python 3.14.6`；FastAPI、HTTPX、Pandas、Streamlit、Uvicorn 可导入。当前解释器未安装 LangGraph，因此工作流测试验证的是项目内置的同顺序确定性回退执行器。 |
| 自动化测试 | 通过 | `python3 -m pytest -q`：`14 passed in 0.75s`。覆盖输入校验、KPI、预警、收入影响恒等式、工作流、API 和 LLM 输出约束。 |
| 语法编译 | 通过 | `python3 -m compileall -q app.py business_analysis_agent tests` 无输出、退出码为零。 |
| wheel 构建 | 通过 | `python3 -m pip wheel --no-deps --no-build-isolation ...` 生成 `business_analysis_agent-0.1.0-py3-none-any.whl`；SHA-256：`a50e8be40e3c4591b61e20afbeb146311c58bb10ac8c696acde4cb22312745da`。`--no-deps` 只验证项目打包，不声称已解析或安装运行依赖。 |
| Streamlit 健康检查 | 通过 | 临时启动仅绑定本机回环地址的服务，`/_stcore/health` 返回 `ok`，随后已停止服务。 |
| 轻量敏感词扫描 | 未发现匹配 | 对源码中常见 API Key/Bearer 字面量模式进行 `rg` 扫描，无匹配。该检查不是完整的密钥管理或安全渗透测试。 |

## 未覆盖项

- 不上传真实或私有业务数据。
- 不配置或调用外部 LLM 服务。
- 不验证真实 LangGraph 依赖环境；当前解释器缺少该依赖，回退执行器已通过测试。
- 不执行 Docker 镜像或生产部署。
