"""Multi-model judge consensus scoring (v2.4).

Lifts `charter/llm_judge_online.py` (single LLM judge) to **consensus**
across N judge backends:

    - `ConsensusJudge` - runs N judge backends (default: Agnes + OpenAI, or
      3 models of one provider) on the same artifacts and aggregates:
        * mean / median per-dimension score
        * majority verdict (pass/fail) with a tie-break rule
        * per-judge agreement matrix (how well the judges agree)
        * overall confidence = 1 - std(normalized scores)
      Result carries `details["judges"]` (per-judge scores) +
      `details["agreement"]` + `details["confidence"]`.
    - Offline-safe: any judge that fails (no key / network) is *excluded*
      from consensus and flagged in `details["excluded"]`; if ALL judges are
      excluded, the consensus falls back to the offline heuristic judge and
      sets `details["mode"] = "offline-fallback"`.

Stdlib-only. The per-judge call reuses `charter.llm_judge_online._parse_judge_json`
and the JudgeBackend protocol, so no duplication.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .evaluation import JUDGE_DIMENSIONS, evaluate_agent
from .llm_judge_online import JudgeBackend, make_judge, _judge_prompt, _parse_judge_json

__all__ = [
    "ConsensusJudge", "consensus_judge", "agreement_matrix",
]


def agreement_matrix(scores_by_judge: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """Per-dimension agreement: 1 - normalized std of the judges' scores.
    Higher = more agreement. Returns one value per dimension + overall."""
    if len(scores_by_judge) < 2:
        # single judge -> agreement is vacuously 1.0
        return {d: 1.0 for d in JUDGE_DIMENSIONS} | {"overall": 1.0}
    per_dim: Dict[str, float] = {}
    for d in JUDGE_DIMENSIONS:
        vals = [s.get(d, 0.5) for s in scores_by_judge.values()]
        mean = statistics.fmean(vals)
        if mean == 0:
            std = 0.0
        else:
            std = statistics.pstdev(vals) / max(0.001, abs(mean))
        per_dim[d] = round(max(0.0, min(1.0, 1.0 - std)), 3)
    vals_all = [v for vs in scores_by_judge.values() for v in vs.values()]
    m_all = statistics.fmean(vals_all)
    std_all = (statistics.pstdev(vals_all) / max(0.001, abs(m_all))) if vals_all else 0.0
    per_dim["overall"] = round(max(0.0, min(1.0, 1.0 - std_all)), 3)
    return per_dim


@dataclass
class ConsensusResult:
    project_id: str
    weighted: float
    passed: bool
    verdict: str
    scores: Dict[str, float]
    n_judges: int
    excluded: List[str] = field(default_factory=list)
    agreement: Dict[str, float] = field(default_factory=dict)
    confidence: float = 1.0
    per_judge: Dict[str, Dict[str, float]] = field(default_factory=dict)
    mode: str = "consensus"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "weighted": self.weighted, "passed": self.passed,
            "verdict": self.verdict, "scores": self.scores,
            "details": {
                "mode": self.mode, "n_judges": self.n_judges,
                "excluded": self.excluded, "agreement": self.agreement,
                "confidence": self.confidence, "per_judge": self.per_judge,
            },
        }


class ConsensusJudge:
    """Run N judge backends and aggregate a consensus verdict."""

    def __init__(self, backends: Optional[List[str]] = None,
                 models: Optional[List[str]] = None,
                 api_key: Optional[str] = None) -> None:
        # Default: agnes + openai; if a model list is given, fan out that
        # many models on the first available provider.
        self.backends = backends or ["agnes", "openai"]
        self.models = models
        self.api_key = api_key
        self._judges = self._build()

    def _build(self) -> List[Any]:
        out = []
        for i, b in enumerate(self.backends):
            model = self.models[i] if self.models and i < len(self.models) else None
            out.append(make_judge(backend=b, api_key=self.api_key, model=model))
        return out

    def run(self, project_id: str, artifacts: Dict[str, Any],
            threshold: float = 0.7) -> ConsensusResult:
        prompt = _judge_prompt(artifacts)
        per_judge: Dict[str, Dict[str, float]] = {}
        excluded: List[str] = []
        for jb in self._judges:
            key = f"{jb.name}" + (f"-{jb.model}" if getattr(jb, "model", None) else "")
            if isinstance(jb, __import__("charter.llm_judge_online", fromlist=["OfflineJudge"]).OfflineJudge):
                # offline backend only used when everything else is excluded
                continue
            try:
                raw = jb.judge(prompt)
                scores = raw["scores"]
                per_judge[key] = scores
            except Exception:
                excluded.append(key)

        if not per_judge:
            # all judges failed -> offline fallback
            base = evaluate_agent(project_id, artifacts, judge=None, threshold=threshold)
            return ConsensusResult(
                project_id=project_id,
                weighted=base.weighted, passed=base.passed, verdict=base.verdict,
                scores=base.scores, n_judges=0, excluded=excluded,
                agreement={d: 1.0 for d in JUDGE_DIMENSIONS} | {"overall": 1.0},
                confidence=0.0, per_judge={}, mode="offline-fallback",
            )

        # aggregate: mean per dimension
        agg_scores: Dict[str, float] = {}
        for d in JUDGE_DIMENSIONS:
            vals = [s.get(d, 0.5) for s in per_judge.values()]
            agg_scores[d] = round(statistics.fmean(vals), 3)
        weights = {"spec_compliance": .25, "code_quality": .25,
                   "test_adequacy": .25, "efficiency": .1, "safety": .15}
        weighted = round(sum(agg_scores[d] * weights[d] for d in JUDGE_DIMENSIONS), 3)
        passed = weighted >= threshold

        # majority verdict
        verdicts = [self._verdict_for(per_judge[k]) for k in per_judge]
        majority = "pass" if verdicts.count("pass") >= len(verdicts) / 2 else "fail"
        if passed != (majority == "pass"):
            # tie-break: trust the weighted mean
            majority = "pass" if passed else "fail"

        agreement = agreement_matrix(per_judge)
        confidence = round(agreement.get("overall", 0.0), 3)
        return ConsensusResult(
            project_id=project_id, weighted=weighted, passed=passed,
            verdict=majority, scores=agg_scores,
            n_judges=len(per_judge), excluded=excluded,
            agreement=agreement, confidence=confidence,
            per_judge=per_judge, mode="consensus",
        )

    @staticmethod
    def _verdict_for(scores: Dict[str, float]) -> str:
        return "pass" if min(scores.values()) >= 0.5 else "fail"


def consensus_judge(
        project_id: str, artifacts: Dict[str, Any],
        backends: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        threshold: float = 0.7,
        api_key: Optional[str] = None) -> Dict[str, Any]:
    """tool: consensus_judge - multi-model judge consensus (v2.4).

    Returns the `ConsensusResult.as_dict()` shape: scores/weighted/passed/
    verdict + details{mode, n_judges, excluded, agreement, confidence,
    per_judge}. Offline-safe: degrades to the heuristic judge when no live
    backends are available.
    """
    cj = ConsensusJudge(backends=backends, models=models, api_key=api_key)
    return cj.run(project_id, artifacts, threshold).as_dict()
