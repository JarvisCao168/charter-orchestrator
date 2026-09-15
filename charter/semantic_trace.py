"""Full-link semantic tracing: input/output similarity + hallucination guard (v3.11).

Lifts the "semantic tracing" idea from the multi-agent consistency design
analysis: instead of only recording *which* tool ran, we also record the
**semantic similarity between a tool call's input and its output**. When the
output drifts too far from the input (e.g. input "query stock price" ->
output "nice weather"), the trace flags it as a *hallucination* and the
guard can intercept it before it poisons downstream state.

Builds on Charter's existing embedding capability (`charter.vector_memory.
hash_embed` for offline / `charter.llm_embed.pick_embedder` for a real model)
so the module is stdlib-safe: with no API key it falls back to the offline
hashing embedder and still produces a cosine-similarity signal.

    - `SemanticSpan` - one traced tool call: input text, output text, the
      computed similarity, and a hallucination verdict.
    - `SemanticTracer` - accumulates spans, computes similarity, and exposes
      `guard(span, threshold)` -> (allowed, verdict) for intercepting.
    - `cosine_similarity(a, b)` - stdlib vector math.

The tracer can wrap `charter.mcp_server.list_mcp_tools()` results or any
tool-call pipeline: every call records a span, and a too-low similarity
yields a `hallucination` finding an orchestrator can log / block.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

__all__ = [
    "SemanticSpan", "SemanticTracer", "cosine_similarity",
    "make_embedder", "TraceVerdict",
]


# ---------------------------------------------------------------------------
# Vector math + embedder resolution
# ---------------------------------------------------------------------------

def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors (0.0 when either is empty)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def make_embedder(provider: str = "auto", dim: int = 256,
                  prefer_offline: bool = True) -> Callable[[str, int], List[float]]:
    """Resolve an embedder.

    Offline-first (deterministic, keeps CI green): when ``prefer_offline`` is
    True (the default) OR no API key is available, the offline hashing
    embedder (``charter.vector_memory.hash_embed``) is returned. A real LLM
    embedder (Agnes / OpenAI) is used only when explicitly requested via
    ``provider="agnes"`` / ``"openai"`` (with ``prefer_offline=False``) AND the
    corresponding API key is present.

    Returns a callable ``(text, dim) -> normalized vector``.
    """
    import os as _os
    explicit_llm = provider in ("agnes", "openai")
    want_llm = explicit_llm and not prefer_offline
    key_present = _os.environ.get("AGNES_API_KEY") if provider == "agnes" else \
                  (_os.environ.get("OPENAI_API_KEY") if provider == "openai" else None)
    if want_llm and key_present:
        try:
            from charter.llm_embed import pick_embedder
            try:
                emb = pick_embedder(provider, agnes={"dim": dim}, openai={"dim": dim})
                def _llm(text: str, d: int = dim) -> List[float]:
                    return emb(text, d)
                return _llm
            except Exception:
                pass
        except Exception:
            pass
    # offline fallback: default, or LLM requested but no key / no network.
    from charter.vector_memory import hash_embed
    def _hash(text: str, d: int = dim) -> List[float]:
        return hash_embed(text, d)
    return _hash


# ---------------------------------------------------------------------------
# Span + verdict
# ---------------------------------------------------------------------------

class TraceVerdict(str):
    OK = "ok"
    HALLUCINATION = "hallucination"
    NEUTRAL = "neutral"


@dataclass
class SemanticSpan:
    """One traced tool/agent call with its semantic input->output drift."""
    span_id: str
    input_text: str
    output_text: str
    similarity: float = 0.0
    verdict: str = TraceVerdict.OK
    ts: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"span_id": self.span_id, "input_text": self.input_text,
                "output_text": self.output_text, "similarity": self.similarity,
                "verdict": self.verdict, "ts": self.ts, "meta": self.meta}


@dataclass
class SemanticTracer:
    """Accumulates semantic spans and gates them on a similarity threshold.

    ``embed`` is a ``(text, dim) -> vector`` callable (use
    :func:`make_embedder`). ``similarity_threshold`` is the minimum input->
    output cosine below which a span is flagged as a hallucination.
    """
    threshold: float = 0.15
    dim: int = 256
    embed: Optional[Callable[[str, int], List[float]]] = None
    spans: List[SemanticSpan] = field(default_factory=list)
    _seq: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if self.embed is None:
            self.embed = make_embedder(dim=self.dim)

    # -- core -------------------------------------------------------
    def record(self, span_id: Optional[str],
               input_text: str, output_text: str,
               **meta: Any) -> SemanticSpan:
        self._seq += 1
        sid = span_id or f"span-{self._seq}"
        vin = self.embed(input_text, self.dim)
        vout = self.embed(output_text, self.dim)
        sim = cosine_similarity(vin, vout)
        verdict = self._judge(sim)
        span = SemanticSpan(span_id=sid, input_text=input_text,
                            output_text=output_text, similarity=sim,
                            verdict=verdict, meta=meta)
        self.spans.append(span)
        return span

    def _judge(self, sim: float) -> str:
        if sim < self.threshold:
            return TraceVerdict.HALLUCINATION
        if sim < self.threshold * 2:
            return TraceVerdict.NEUTRAL
        return TraceVerdict.OK

    # -- guard ------------------------------------------------------
    def guard(self, span: SemanticSpan) -> Dict[str, Any]:
        """Decide whether a span may proceed. A hallucination verdict is
        intercepted (``allowed=False``); others pass through."""
        allowed = span.verdict != TraceVerdict.HALLUCINATION
        return {"allowed": allowed, "span_id": span.span_id,
                "verdict": span.verdict, "similarity": span.similarity}

    # -- introspection ---------------------------------------------
    def hallucinations(self) -> List[SemanticSpan]:
        return [s for s in self.spans if s.verdict == TraceVerdict.HALLUCINATION]

    def summary(self) -> Dict[str, Any]:
        return {
            "spans": len(self.spans),
            "hallucinations": len(self.hallucinations()),
            "avg_similarity": (sum(s.similarity for s in self.spans) / len(self.spans)
                               if self.spans else 0.0),
            "threshold": self.threshold,
        }
