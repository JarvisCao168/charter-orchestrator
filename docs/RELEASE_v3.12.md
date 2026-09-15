# v3.12.0 — Critic 修复后重跑闭环 + SemanticCache 持久化落盘

发布日期：2026-09-15

## ① Critic 修复后重跑闭环（`charter/critic_agent.py`）

把 Critic 从"一次性 reflect"升级为"reflect → 注入补丁 → 重跑"的自愈闭环：

- `Critic.apply_repairs(plan, repairs)`：把一组修复补丁注入 plan，返回**新的** plan（原 plan 不被改动，保留可审计/可重放）。支持的 patch 动作：
  - `insert_step`（为悬挂依赖补 stub 步骤）
  - `break_cycle`（断开环中的一条边）
  - `dedupe_artifact`（重复产出只留 keeper）
  - `attach_step` / `flag`（不改变结构）
- `Critic.reflect_until_sound(plan, outputs, max_rounds)`：闭环驱动——每轮 reflect 产生补丁 → `apply_repairs` 注入新 plan → 再 reflect，直到 plan **sound** 或达到 `max_rounds`。返回的 `CriticReport` 新增字段：
  - `rounds`（实际重跑轮数，干净 plan 为 0）
  - `history`（每轮的 pre/post/repairs/steps 摘要）
  - `converged`（是否以 sound 收尾）
  - `final_plan`（最后一版补丁注入后的 plan dict）
- `CriticReport` 同步扩展上述四个字段，`to_dict()` 一并输出
- 7 个新测试（insert stub / break cycle / dedupe / dangling 收敛 / cycle 收敛 / 干净 plan 零轮 / max_rounds 约束）

## ② SemanticCache 持久化落盘（`charter/model_router.py`）

把 `SemanticCache` 从纯内存 LRU 升级为**两级缓存（内存 LRU + SQLite 落盘）**，复用 `charter.embed_cache.EmbedCache` 的 SQLite store 模式：

- `SemanticCache(semantic_key, max_entries, disk_path)`：传 `disk_path` 时自动建 `semantic_cache` 表（WAL 模式），
  - `put` 同时写内存 + 落盘
  - `get` 内存 miss 时回查磁盘并回填内存（hit 计数区分内存/磁盘来源）
- `close()` / `is_persistent()` / `stats()["disk_enabled"]` / `stats()["disk_path"]`
- **跨进程语义缓存**：新进程打开同一 SQLite 文件即可读回上一次的缓存，实现文档中"结果语义缓存降本"的跨进程落地
- 5 个新测试（跨进程持久化 / 无 disk 纯内存 / 内存被 LRU 逐出后磁盘回读 / 自定义 key 持久化 / close 幂等）

## 元数据
- 版本 3.11.0 → 3.12.0；导出 `apply_repairs` / `reflect_until_sound`（模块级便捷名）
- 总测试 455 → 469（+7 Critic 闭环 +5 SemanticCache 持久化 +2 版本调整）
- 3.9 / 3.11 / 3.12 全绿

## 架构借鉴
本版本对应《多Agent系统架构设计分析报告》进阶设计的两点收尾：
- ① Critic 闭环 = "动态修复"真正落地：Critic Agent 不再只"报告+降级"，而是**生成修复补丁并注入 DAG 重跑**，直到结构收敛——"报错变自愈"
- ② SemanticCache 落盘 = "语义缓存降本"的跨进程持久化形态：简单任务命中缓存直接返回，避免重复烧 token
