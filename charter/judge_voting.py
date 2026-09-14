"""Multi-provider judge weighted voting (v2.5).

Lifts `charter/judge_consensus.py` (equal-weight mean / majority) to
**weighted voting**: each judge provider casts a vote, and the consensus is a
weighted aggregation where the weight of a provider reflects its
*historical accuracy* (measured against a labeled gold set) or a configured
explicit weight. A provider that has never been measured falls back to a
default weight, so the function is usable out of the box.

    - `ProviderVote` - one provider's per-dimension scores + verdict + weight.
    - `WeightedVotingJudge` - aggregate N ProviderVotes:
        * weighted mean per dimension
        * weighted majority verdict
        * per-provider contribution (weight / total)
        * effective-agreement (weighted 1 - normalized std)
    - `accuracy_weights(gold)` - compute weights from a labeled gold set
      (providers scoring closer to the gold verdict get higher weight).

Stdlib-only. Offline-safe: the aggregator is pure math over the supplied
votes; `vote_judges(...)` is the convenience entry that runs the live judges
(first) and then aggregates.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .evaluation import JUDGE_DIMENSIONS, evaluate_agent
from .llm_judge_online import JudgeBackend, make_judge, _judge_prompt

__all__ = [
    "ProviderVote", "WeightedVotingJudge", "vote_judges", "accuracy_weights",
]


@dataclass
class ProviderVote:
    provider: str
    scores: Dict[str, float]
    verdict: str
    weight: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> Dict[str, float]:
        return {d: max(0.0, min(1.0, self.scores.get(d, 0.5)))
                for d in JUDGE_DIMENSIONS}


class WeightedVotingJudge:
    """Aggregate provider votes into a weighted consensus."""

    def __init__(self, default_weight: float = 1.0,
                 threshold: float = 0.7) -> None:
        self.default_weight = default_weight
        self.threshold = threshold
        self._weights: Dict[str, float] = {}

    def set_weights(self, weights: Dict[str, float]) -> "WeightedVotingJudge":
        """Explicit per-provider weights (override default)."""
        self._weights = dict(weights)
        return self

    def weighted(self, provider: str) -> float:
        return self._weights.get(provider, self.default_weight)

    def aggregate(self, votes: Sequence[ProviderVote]) -> Dict[str, Any]:
        """Weighted mean per-dim + weighted majority verdict + contributions."""
        if not votes:
            base = evaluate_agent(
                "weighted", {"test_coverage": 0, "violations": [],
                              "tests_written": False, "token_ratio": 1.0},
                judge=None, threshold=self.threshold)
            return {
                "weighted": base.weighted, "passed": base.passed,
                "verdict": base.verdict, "scores": base.scores,
                "n_providers": 0,
                "details": {"mode": "no-votes-fallback",
                            "n_providers": 0, "contributions": {},
                            "effective_agreement": 0.0, "votes": []},
            }

        total_w = sum(v.weight for v in votes) or 1.0

        # weighted mean per dimension
        wmean: Dict[str, float] = {}
        for d in JUDGE_DIMENSIONS:
            nums = [v.normalized()[d] * v.weight for v in votes]
            wmean[d] = round(sum(nums) / total_w, 4)
        weights_map = {"spec_compliance": .25, "code_quality": .25,
                       "test_adequacy": .25, "efficiency": .1, "safety": .15}
        overall = round(sum(wmean[d] * weights_map[d]
                            for d in JUDGE_DIMENSIONS), 4)
        passed = overall >= self.threshold

        # weighted majority verdict
        w_pass = sum(v.weight for v in votes if v.verdict == "pass")
        majority = "pass" if w_pass >= total_w / 2 else "fail"
        verdict = "pass" if passed else "fail"  # trust the weighted mean
        if majority != verdict:
            verdict = majority  # tie-break toward majority

        # effective agreement: 1 - weighted normalized std of all dim values
        wmean_all = (sum(v.normalized()[d] * v.weight
                          for v in votes for d in JUDGE_DIMENSIONS)
                     / total_w)
        wvar = sum((v.normalized()[d] - wmean_all) ** 2 * v.weight
                   for v in votes for d in JUDGE_DIMENSIONS) / total_w
        wstd = statistics.sqrt(wvar) if wvar > 0 else 0.0
        eff_agree = round(max(0.0, min(1.0, 1.0 - wstd)), 4)

        contributions = {v.provider: round(v.weight / total_w, 4)
                         for v in votes}
        return {
            "project_id": "weighted",
            "weighted": overall,
            "passed": passed,
            "verdict": verdict,
            "scores": wmean,
            "n_providers": len(votes),
            "details": {
                "mode": "weighted-voting",
                "n_providers": len(votes),
                "total_weight": round(total_w, 4),
                "contributions": contributions,
                "effective_agreement": eff_agree,
                "votes": [{
                    "provider": v.provider, "verdict": v.verdict,
                    "weight": v.weight, "scores": v.normalized()}
                    for v in votes],
            },
        }


def accuracy_weights(gold: Dict[str, Dict[str, float]],
                     provider_scores: Dict[str, Dict[str, Dict[str, float]]],
                     top_k: int = 3) -> Dict[str, float]:
    """Compute per-provider weights from a labeled gold set.

    `gold` maps sample_id -> per-dimension gold scores. `provider_scores`
    maps provider -> sample_id -> its per-dimension scores. A provider's
    weight = 1 + (1 - mean absolute error vs gold), so a more accurate
    provider votes harder. `top_k` trims to the top-K providers by accuracy.
    """
    per_provider_mae: Dict[str, float] = {}
    for provider, samples in provider_scores.items():
        errs = []
        for sid, scores in samples.items():
            g = gold.get(sid)
            if not g:
                continue
            for d, gv in g.items():
                pv = scores.get(d, 0.5)
                errs.append(abs(float(gv) - float(pv)))
        per_provider_mae[provider] = (statistics.fmean(errs)
                                      if errs else 0.5)
    # weight: lower MAE -> higher weight
    raw = {p: (1.0 + max(0.0, 1.0 - mae))
           for p, mae in per_provider_mae.items()}
    # trim to top_k providers (highest weight)
    ranked = sorted(raw.items(), key=lambda kv: kv[1], reverse=True)
    return dict(ranked[:top_k]) if ranked else {"default": 1.0}


def vote_judges(
        project_id: str, artifacts: Dict[str, Any],
        backends: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.7,
        api_key: Optional[str] = None) -> Dict[str, Any]:
    """tool: vote_judges - run providers and aggregate via weighted voting.

    Runs each backend in `backends` (default ["agnes", "openai"]), collects
    a `ProviderVote` per successful backend, then aggregates with
    `WeightedVotingJudge` (optional per-provider `weights`). Offline-safe:
    backends that fail to run are simply excluded from the vote; if none
    succeed the aggregation falls back to the heuristic judge.
    """
    backends = backends or ["agnes", "openai"]
    prompt = _judge_prompt(artifacts)
    votes: List[ProviderVote] = []
    for i, b in enumerate(backends):
        model = models[i] if models and i < len(models) else None
        jb = make_judge(backend=b, api_key=api_key, model=model)
        if type(jb).__name__ == "OfflineJudge":
            continue
        key = f"{jb.name}" + (f"-{jb.model}" if getattr(jb, "model", None) else "")
        try:
            raw = jb.judge(prompt)
            votes.append(ProviderVote(
                provider=key, scores=raw["scores"],
                verdict=raw.get("verdict", "pass")))
        except Exception:
            continue  # excluded from the vote

    judge = WeightedVotingJudge(threshold=threshold)
    if weights:
        judge.set_weights(weights)
    # default weight; per-provider weight can be set from accuracy_weights()
    result = judge.aggregate(votes)
    result["project_id"] = project_id
    result["details"]["excluded"] = [b for b in backends
                                     if b not in
                                     [v.provider.split("-")[0] for v in votes]]
    return result
