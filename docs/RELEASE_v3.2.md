# v3.2.0 — 107 Skills + MCP SSE/HTTP 传输

发布日期：2026-09-15

## 新增

### 技能扩量：47 → 107（+60）
- 基于现有 58 个 charter 模块生成 60 个结构化 skill（9 大类全部扩量）：
  - dev +8（multilang / SPIRE gRPC / bidir mTLS K8s / regression / OnCall gRPC / delivery payload / IAM bundle / RBAC）
  - security +8（X509 PKI / SPIFFE trust domain / SVID / attestation / mTLS / bidir mTLS / K8s node socket / socket-pair SVID）
  - obs +10（OTel Jaeger / trace link / Tempo / Grafana / Prometheus / Mimir / SLO gate / AlertManager / OnCall routing / OnCall gRPC E2E）
  - collab +8（cross-session memory / compress / hierarchy / clustering / cross-language merge / vector merge / PR scoring / PR sentiment）
  - analysis +6（judge consensus / weighted voting / concurrency+cache / LLM embedder / embed cache / cluster naming）
  - test +6（diff hunk completion / cross-hunk consistency / tree-sitter semantics / auto-suggester / IAM policy / IAM drift remediate）
  - deploy +8（judge pool plan / cost autoscaler / live+S3 / K8s deploy / template PR bot / PR+CI gate / checkpoint S3 / cross-repo bus）
  - tool +6（template marketplace / PR validate / vector memory / agent identity / K8s templates / sandbox-dropbox-lifecycle）
- `skills/manifest.json`：107 条，每条含 module 引用（映射到具体 charter 模块）
- `scripts/validate_skills.py`：校验阈值 47 → 107
- `SKILL.md` frontmatter：`charter-skills.total` 47 → 107（按 9 类分项）

### MCP SSE/HTTP 传输（`charter/mcp_server.py`）
- 新增 `HTTPMCPServer` + `run_http_server()`：纯 stdlib（`http.server` + `threading` + `queue`），零外部依赖
- 端点：
  - `GET /mcp/health` — liveness probe
  - `GET /mcp/tools` — 返回 20 工具定义
  - `GET /mcp/sse` — SSE 流：初始 "endpoint" 事件 + 后续 "message" 事件
  - `POST /mcp/message?client=<cid>` — JSON-RPC 请求，结果经 SSE 回推
- 启动：`python -c "from charter.mcp_server import run_http_server; run_http_server('0.0.0.0', 8765)"`
- 5 个新测试（HTTPMCPServer 构造 + 107 resources + tools shape + manifest 路径 + 类别计数）

### 测试
- 260 → 292（+32：107 skill 路径/类别校验 + SSE/HTTP 传输 5 + 原 27 MCP 测试更新为 107 断言）
- 3.9 / 3.11 / 3.12 全绿

## 元数据
- `pyproject.toml` 3.1.0 → 3.2.0
- `charter/__init__.py` `__version__` → 3.2.0
- `charter/mcp_server.py` serverInfo.version → 3.2.0
