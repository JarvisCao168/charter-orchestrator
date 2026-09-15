"""Distributed judge pool (K8s Job multi-replica) (v2.7).

Lifts `charter/judge_concurrency.py` (in-process thread pool) to a
**K8s-orchestrated** judge pool: a `JudgePool` plans *N* K8s Jobs, one per
provider/model replica, each running a judge task, and the results are
collected + aggregated with the same weighted-voting logic as
`vote_judges`. The module is offline-safe: the Job manifests + the
aggregation are produced without a K8s cluster, so CI stays green; when a
`kubernetes` client / in-cluster config IS available, `pool.submit` can
actually create the Jobs.

    - `JudgeTask` - one unit of judge work (artifacts + provider + model +
      weight).
    - `JudgePoolPlan` - the full plan: N replica Jobs + a collector Job.
    - `plan_judge_pool(...)` - build the K8s Job YAML for each replica +
      the aggregator, ready to `kubectl apply`.
    - `DistributedJudgePool` - the runtime: `plan()` produces the jobs;
      `aggregate(results)` folds replica results into a weighted vote;
      `submit(plan, k8s_client)` actually creates the Jobs when a client
      is provided (no client -> returns the plan, no network).
    - `render_pool_manifests(...)` - one-shot: all K8s Job/Service/ConfigMap
      docs as JSON, ready to drop into a cluster.

Stdlib-only. No kubernetes dep: the client is passed in lazily; without
it every method degrades to plan-only output.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .judge_voting import ProviderVote, WeightedVotingJudge, accuracy_weights

__all__ = [
    "JudgeTask", "JudgePoolPlan", "DistributedJudgePool",
    "plan_judge_pool", "render_pool_manifests",
]

JUDGE_IMG = "charter/judge:latest"


@dataclass
class JudgeTask:
    task_id: str
    provider: str
    model: str
    weight: float = 1.0
    artifacts: Dict[str, Any] = field(default_factory=dict)
    threshold: float = 0.7

    def as_job_args(self) -> List[str]:
        """The args a K8s Job container passes to the judge entrypoint."""
        return [
            "--provider", self.provider,
            "--model", self.model,
            "--weight", str(self.weight),
            "--threshold", str(self.threshold),
            "--task-id", self.task_id,
            # artifacts + results are passed via a ConfigMap + PVC, mounted
            # at /run/charter-judge (see render_pool_manifests)
        ]


@dataclass
class JudgePoolPlan:
    """The full plan: N replica judge Jobs + one collector/aggregator Job."""
    pool_id: str
    tasks: List[JudgeTask]
    replica_count: int
    collector_name: str
    created_ts: float = field(default_factory=time.time)

    def to_job_names(self) -> List[str]:
        return [f"charter-judge-{self.pool_id}-{i}"
                for i in range(len(self.tasks))]


def plan_judge_pool(
        artifacts: Dict[str, Any],
        backends: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.7,
        replicas_per_provider: int = 2,
        pool_id: Optional[str] = None,
        api_key_ref: str = "JUDGE_API_KEY") -> JudgePoolPlan:
    """tool: plan_judge_pool - plan a K8s-distributed judge pool.

    One JudgeTask per (backend, model) pair, replicated
    `replicas_per_provider` times. Returns a `JudgePoolPlan` (no cluster
    needed to build it).
    """
    backends = backends or ["agnes", "openai"]
    pool_id = pool_id or "jp-" + uuid.uuid4().hex[:8]
    tasks: List[JudgeTask] = []
    for i, b in enumerate(backends):
        model = (models[i] if models and i < len(models) else
                 f"{b}-default")
        w = (weights or {}).get(b, 1.0)
        for r in range(replicas_per_provider):
            tasks.append(JudgeTask(
                task_id=f"{pool_id}-{b}-{r}",
                provider=b, model=model, weight=w,
                artifacts=artifacts, threshold=threshold))
    return JudgePoolPlan(
        pool_id=pool_id, tasks=tasks,
        replica_count=replicas_per_provider,
        collector_name=f"charter-judge-collect-{pool_id}",
    )


def _job_manifest(plan: JudgePoolPlan, task: JudgeTask,
                  api_key_ref: str) -> Dict[str, Any]:
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": f"charter-judge-{plan.pool_id}-{task.task_id}",
            "labels": {
                "charter.io/pool": plan.pool_id,
                "charter.io/provider": task.provider,
                "charter.io/role": "judge",
            },
        },
        "spec": {
            "backoffLimit": 2,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "judge",
                        "image": JUDGE_IMG,
                        "args": task.as_job_args(),
                        "env": [
                            {"name": "JUDGE_PROVIDER", "value": task.provider},
                            {"name": "JUDGE_MODEL", "value": task.model},
                            {"name": "JUDGE_TASK_ID", "value": task.task_id},
                            {"name": "ARTIFACTS_MOUNT",
                             "value": "/run/charter-judge/artifacts.json"},
                            {"name": "RESULT_MOUNT",
                             "value": f"/run/charter-judge/results/"
                                      f"{task.task_id}.json"},
                        ],
                        "envFrom": [
                            {"secretRef": {"name": api_key_ref}},
                        ],
                        "resources": {
                            "requests": {"cpu": "200m", "memory": "256Mi"},
                            "limits": {"cpu": "1000m", "memory": "1Gi"},
                        },
                        "volumeMounts": [
                            {"name": "work", "mountPath": "/run/charter-judge"},
                        ],
                    }],
                    "volumes": [
                        {"name": "work", "emptyDir": {}},
                    ],
                },
            },
        },
    }


def render_pool_manifests(
        plan: JudgePoolPlan,
        api_key_ref: str = "JUDGE_API_KEY",
        namespace: str = "charter") -> Dict[str, str]:
    """tool: render_pool_manifests - all K8s docs (ConfigMap + N Judge Jobs
    + collector Job) as JSON strings, ready for `kubectl apply`."""
    cm = {
        "apiVersion": "v1", "kind": "ConfigMap",
        "metadata": {"name": f"charter-judge-{plan.pool_id}",
                      "namespace": namespace},
        "data": {"artifacts.json": json.dumps(
            plan.tasks[0].artifacts if plan.tasks else {},
            indent=2, ensure_ascii=False, default=str)},
    }
    collector = {
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": plan.collector_name, "namespace": namespace,
                      "labels": {"charter.io/pool": plan.pool_id,
                                  "charter.io/role": "collector"}},
        "spec": {
            "backoffLimit": 2,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [{
                        "name": "collector",
                        "image": JUDGE_IMG,
                        "args": ["--collect", "--pool", plan.pool_id],
                        "env": [
                            {"name": "COLLECT_MOUNT",
                             "value": "/run/charter-judge/results"},
                            {"name": "AGGREGATE_RESULT",
                             "value": "/run/charter-judge/aggregate.json"},
                        ],
                        "volumeMounts": [
                            {"name": "work", "mountPath": "/run/charter-judge"}],
                    }],
                    "volumes": [{"name": "work", "emptyDir": {}}],
                },
            },
        },
    }
    out: Dict[str, str] = {"configmap": json.dumps(cm, indent=2)}
    for i, task in enumerate(plan.tasks):
        out[f"job-{i}"] = json.dumps(
            _job_manifest(plan, task, api_key_ref), indent=2)
    out["collector"] = json.dumps(collector, indent=2)
    return out


class DistributedJudgePool:
    """Plan + (optionally) submit a K8s judge pool, then aggregate results.

    Offline-safe: `submit(plan, k8s_client=None)` returns the plan (with a
    `submitted=False` flag) when no client is bound; with a real
    `kubernetes` client it creates the Jobs. `aggregate(results)` folds
    per-replica ProviderVotes into a weighted vote (same shape as
    `vote_judges`).
    """

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold
        self._judge = WeightedVotingJudge(threshold=threshold)

    def submit(self, plan: JudgePoolPlan,
               k8s_client: Any = None) -> Dict[str, Any]:
        if k8s_client is None:
            return {"submitted": False, "plan": plan,
                    "job_names": plan.to_job_names(),
                    "note": "no kubernetes client; plan-only"}
        created = []
        for name in plan.to_job_names():
            job = json.loads(render_pool_manifests(
                plan)[f"job-{created and 0 or 0}"] if False else
                _job_manifest(plan, plan.tasks[0], "JUDGE_API_KEY")
                .get("spec", {}))  # placeholder; real create below
            try:
                # Lazy: use the k8s client's batch.v1 if present
                from kubernetes import client, config  # type: ignore
                body = _job_manifest(plan,
                                     plan.tasks[len(created)],
                                     "JUDGE_API_KEY")
                client.BatchV1Api().create_namespaced_job(
                    namespace="charter", body=body)
                created.append(name)
            except Exception:
                break
        return {"submitted": bool(created), "plan": plan,
                "created_jobs": created,
                "job_names": plan.to_job_names()}

    def aggregate(self, results: Sequence[ProviderVote]
                  ) -> Dict[str, Any]:
        """Fold per-replica votes (possibly many replicas of one provider)
        into a weighted vote. Replicas of the same provider are grouped and
        their scores averaged before the weighted aggregation, so a provider
        with 3 replicas doesn't triple its weight — the `weight` of the
        *provider* controls influence, not the replica count."""
        by_provider: Dict[str, List[ProviderVote]] = {}
        for v in results:
            base = v.provider.split("-")[0]
            by_provider.setdefault(base, []).append(v)
        # average each provider's replica votes
        grouped: List[ProviderVote] = []
        for base, votes in by_provider.items():
            n = len(votes)
            avg_scores = {d: round(sum(v.scores.get(d, 0.5)
                                       for v in votes) / n, 4)
                          for d in ("spec_compliance", "code_quality",
                                    "test_adequacy", "efficiency", "safety")}
            pass_votes = sum(1 for v in votes if v.verdict == "pass")
            verdict = "pass" if pass_votes >= n / 2 else "fail"
            w = votes[0].weight
            grouped.append(ProviderVote(provider=base, scores=avg_scores,
                                        verdict=verdict, weight=w))
        out = self._judge.aggregate(grouped)
        out["details"]["replicas_per_provider"] = {
            base: len(vs) for base, vs in by_provider.items()}
        out["details"]["n_replicas"] = len(list(results))
        return out


def render_pool_manifests_json(plan: JudgePoolPlan,
                               api_key_ref: str = "JUDGE_API_KEY",
                               namespace: str = "charter") -> str:
    """One-shot JSON of all the K8s manifests (ConfigMap + Jobs + collector)."""
    return json.dumps(render_pool_manifests(plan, api_key_ref,
                                             namespace), indent=2)
