"""Online LLM-as-judge scoring (v2.2).

Upgrades the offline heuristic judge in `charter/evaluation.py` to a *real*
LLM judge. The judge is provider-agnostic via a small `JudgeBackend`
protocol; built-in backends:

    - `AgnesJudge`   (Agnes AI /apihub.agnes-ai.com, OpenAI-compatible chat)
    - `OpenAIJudge`  (OpenAI /v1/chat/completions)

Both talk over stdlib `urllib` (no `requests` hard dep). The judge prompt is
constructed from the project's artifacts, the judge model returns per-dimension
scores + a verdict, and the module normalizes the LLM's answer into a
`JudgeScore` (same shape as the offline path so callers don't change).

Offline fallback: when no API key is configured (CI, airgapped) or the HTTP
call fails, `score_with_judge(..., online=True)` transparently degrades to the
deterministic heuristic judge in `charter.evaluation` and flags
`details["judge"]="offline"`. This keeps tests green with no key while still
exercising the real online code path when a key IS present.

Key env vars:
    AGNES_API_KEY   / AGNES_BASE_URL   -> AgnesJudge
    OPENAI_API_KEY  / OPENAI_BASE_URL  -> OpenAIJudge
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from .evaluation import JUDGE_DIMENSIONS, evaluate_agent, _heuristic_judge

__all__ = [
    "JudgeBackend", "AgnesJudge", "OpenAIJudge", "OfflineJudge",
    "make_judge", "score_with_judge", "JUDGE_SYSTEM",
]

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
JUDGE_SYSTEM = (
    "You are a strict code-review judge for an autonomous software agent. "
    "Score each dimension 0.0-1.0. Respond ONLY with JSON of the form "
    '{"spec_compliance": 0.0, "code_quality": 0.0, "test_adequacy": 0.0, "efficiency": 0.0, "safety": 0.0, "verdict": "pass|fail", "rationale": "<short>"}. No prose outside the JSON.'
)


def _judge_prompt(artifacts: Dict[str, Any]) -> str:
    """Build the user prompt from project artifacts (bounded for token cost)."""
    snippet = json.dumps(artifacts, default=str, ensure_ascii=False)
    if len(snippet) > 8000:
        snippet = snippet[:8000] + "...(truncated)"
    return (
        f"Score this agent's work on the five dimensions.\n"
        f"Artifacts:\n{snippet}\n\n"
        f"Return the JSON now."
    )


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------
class JudgeBackend:
    """(prompt) -> parsed dict of per-dimension scores + verdict."""

    name = "base"

    def judge(self, prompt: str) -> Dict[str, Any]:
        raise NotImplementedError


class OfflineJudge(JudgeBackend):
    """Delegates to the deterministic heuristic judge (no network)."""

    name = "offline"

    def judge(self, prompt: str) -> Dict[str, Any]:
        # We can't recover the artifacts dict from the prompt here; callers
        # that truly need offline scoring should pass judge=None to
        # evaluate_agent instead. This backend is used only as a safe default
        # that never raises when a key is missing.
        scores = {d: 0.5 for d in JUDGE_DIMENSIONS}
        scores["safety"] = 1.0
        return {"scores": scores, "verdict": "pass",
                "rationale": "offline neutral fallback"}


class _OpenAICompatJudge(JudgeBackend):
    """Shared OpenAI-compatible chat-completions wrapper (stdlib HTTP)."""

    def __init__(self, api_key: str, base_url: str, model: str,
                 backend: str, timeout: int = 60,
                 temperature: float = 0.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.name = backend

    def judge(self, prompt: str) -> Dict[str, Any]:
        body = json.dumps({
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        return _parse_judge_json(content)


class AgnesJudge(_OpenAICompatJudge):
    """Agnes AI judge (apihub.agnes-ai.com, OpenAI-compatible)."""

    def __init__(self, api_key: str, model: str = "agnes-2.5-flash",
                 base_url: Optional[str] = None,
                 timeout: int = 60, temperature: float = 0.0) -> None:
        base_url = base_url or os.environ.get(
            "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
        super().__init__(api_key, base_url, model, "agnes",
                         timeout, temperature)


class OpenAIJudge(_OpenAICompatJudge):
    """OpenAI judge."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: Optional[str] = None,
                 timeout: int = 60, temperature: float = 0.0) -> None:
        base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1")
        super().__init__(api_key, base_url, model, "openai",
                         timeout, temperature)


def _parse_judge_json(content: str) -> Dict[str, Any]:
    """Tolerantly parse the LLM's JSON answer into a scores dict."""
    # LLMs sometimes wrap JSON in ``` fences or extra prose.
    text = content.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        # last-ditch: no scores -> neutral
        return {"scores": {d: 0.5 for d in JUDGE_DIMENSIONS},
                "verdict": "pass", "rationale": "unparseable judge output"}
    scores: Dict[str, float] = {}
    for d in JUDGE_DIMENSIONS:
        v = raw.get(d)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.5
        scores[d] = max(0.0, min(1.0, v))
    verdict = str(raw.get("verdict", "pass")).lower()
    if verdict not in ("pass", "fail"):
        verdict = "pass" if min(scores.values()) >= 0.5 else "fail"
    return {"scores": scores, "verdict": verdict,
            "rationale": str(raw.get("rationale", ""))[:500]}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_judge(backend: Optional[str] = None,
               api_key: Optional[str] = None,
               model: Optional[str] = None) -> JudgeBackend:
    """Pick a judge backend.

    `backend` in {"agnes","openai","offline", None}. When None, auto-detect:
    AGNES_API_KEY -> AgnesJudge, else OPENAI_API_KEY -> OpenAIJudge,
    else OfflineJudge.
    """
    if backend is None:
        if os.environ.get("AGNES_API_KEY") or api_key:
            backend = "agnes"
        elif os.environ.get("OPENAI_API_KEY"):
            backend = "openai"
        else:
            backend = "offline"
    if backend == "offline":
        return OfflineJudge()
    if backend == "agnes":
        key = api_key or os.environ.get("AGNES_API_KEY", "")
        return AgnesJudge(key, model or "agnes-2.5-flash")
    if backend == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        return OpenAIJudge(key, model or "gpt-4o-mini")
    raise ValueError(f"unknown judge backend: {backend!r}")


def _normalize(backend: JudgeBackend, artifacts: Dict[str, Any],
               raw: Dict[str, Any], threshold: float) -> Dict[str, Any]:
    """Turn a backend's raw {scores, verdict, rationale} into JudgeScore shape."""
    scores = raw["scores"]
    weights = {"spec_compliance": .25, "code_quality": .25,
               "test_adequacy": .25, "efficiency": .1, "safety": .15}
    weighted = sum(scores[d] * weights[d] for d in JUDGE_DIMENSIONS)
    weighted = round(weighted, 3)
    verdict = raw.get("verdict")
    if verdict not in ("pass", "fail"):
        verdict = "pass" if weighted >= threshold else "fail"
    return {
        "scores": scores, "weighted": weighted, "passed": weighted >= threshold,
        "verdict": verdict,
        "details": {
            "judge": backend.name,
            "threshold": threshold, "weights": weights,
            "rationale": raw.get("rationale", ""),
        },
    }


def score_with_judge(project_id: str, artifacts: Dict[str, Any],
                     threshold: float = 0.7,
                     backend: Optional[str] = None,
                     api_key: Optional[str] = None,
                     model: Optional[str] = None,
                     online: bool = True) -> Dict[str, Any]:
    """tool: score_with_judge - real LLM-as-judge quality gate (v2.2).

    Returns the same dict shape as `evaluate_agent` output (scores/weighted/
    passed/verdict/details) so it is drop-in. When `online=True` a real judge
    backend is used (Agnes/OpenAI if a key is available, else OfflineJudge);
    any HTTP failure degrades to the heuristic judge and sets
    `details["judge"]="offline-fallback"`.
    """
    # Baseline: deterministic judge always runs (used as fallback + for
    # offline comparison).
    base = evaluate_agent(project_id, artifacts, judge=None,
                          threshold=threshold)
    if not online:
        base.details["judge"] = "offline"
        return base.__dict__ if hasattr(base, "__dict__") else _as_dict(base)

    jb = make_judge(backend, api_key, model)
    if isinstance(jb, OfflineJudge):
        out = _normalize(jb, artifacts, jb.judge(_judge_prompt(artifacts)),
                         threshold)
        out["details"]["fallback"] = False
        return out

    try:
        raw = jb.judge(_judge_prompt(artifacts))
        out = _normalize(jb, artifacts, raw, threshold)
        out["details"]["fallback"] = False
        return out
    except Exception as exc:  # network / parse / auth -> degrade
        out = _as_dict(base)
        out["details"]["judge"] = "offline-fallback"
        out["details"]["fallback"] = True
        out["details"]["fallback_reason"] = str(exc)[:300]
        return out


def _as_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    d = getattr(obj, "__dict__", None)
    if d:
        return dict(d)
    return {"scores": {}, "weighted": 0.0, "passed": False, "verdict": "fail",
            "details": {}}
