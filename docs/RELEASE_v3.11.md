# v3.11.0 — 四大治理模块落地（事件溯源/反思/语义追踪/成本路由）

发布日期：2026-09-15

基于《多Agent系统数据一致性与高可靠协同架构设计分析报告》的进阶设计，
本版本将四大能力从理念落地为可执行、可测试的 Charter 模块：

## ① validation_gateway.py — 三层校验网关 + 熔断器
- 第一层 `check_contract`（schema 契约：必填字段 + 类型 + bool 不混 int）
- 第二层 `check_data_alignment`（数据对齐：防"500亿→1200亿"漂移，相对容差）
- 第三层 `check_consistency`（一致性：增长/下降等语义矛盾检测）
- `ValidationGateway.check_with_retry(producer)` 本地重试 N 次后降级（填默认值），绝不崩链路
- `CircuitBreaker`（closed/open/half-open，冷却时间，按工具维度隔离故障）
- 21 个测试

## ② critic_agent.py — 全局反思器 + 动态修复
- `Critic.pre_check(plan)`：结构审查（悬挂依赖、环检测、重复产出、孤立节点）
- `Critic.post_audit(plan, outputs, rules)`：逻辑审查 + 可插拔自定义规则
- `Critic.repair(finding)`：生成结构化修复补丁（insert_step / break_cycle / dedupe），把"报错"变"自愈"
- `Critic.reflect(plan, outputs)`：一次调用折叠为 CriticReport
- 7 个测试

## ③ semantic_trace.py — 全链路语义追踪 + 幻觉拦截
- `SemanticTracer.record(span_id, in, out)`：计算输入→输出 embedding 余弦相似度
- `SemanticTracer.guard(span)`：相似度 < 阈值判 hallucination 并拦截
- `make_embedder()`：有 API key 走 LLM embedding，无则离线 hashing embedder（CI 仍绿）
- 9 个测试

## ④ model_router.py — 小模型路由 + 语义缓存（成本管控）
- `TaskProfile.complexity()`：depth/fan_in/risk/tokens/reasoning 合成 0-100 分
- `ModelRouter.route(profile)`：选最便宜的合格 tier（small/medium/large）
- `SemanticCache`：有界 LRU + 语义 hash key + hit-rate 统计
- 14 个测试

## 接线
- `charter/__init__.py`：导出全部 4 个模块的公开 API + `_snapshot_watch_report`
- `charter/mcp_server.py`：`tools/call` 现可选经 `ValidationGateway` + `SemanticTracer` 治理
- `charter/demo_skill.py`：新增 `gov_01..gov_04` 四个治理 skill，`_demo_governance` 一条命令跑通全链路
- `skills/manifest.json`：107 → 111 skills（+4 governance）；`validate_skills.py` 阈值同步

## 元数据
- 版本 3.10.0 → 3.11.0；导出 24 个 v3.11 符号
- 总测试 402 → 455（+53 新增：21+7+9+14+2）
- 3.9 / 3.11 / 3.12 全绿
