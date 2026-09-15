"""LLM / model embedding backend for VectorMemory (v2.1).

Replaces the offline hashing embedder with a *semantic* one. The embedder is
pluggable: pass `llm_embedder(...)` as the `embed` argument to
`charter.vector_memory.VectorMemory` and every recall becomes true semantic
search instead of bag-of-ngrams cosine.

Provider-agnostic via a small `Embedder` protocol. Builtin backends:
    - `AgnesEmbedder`  (Agnes AI /api/embeddings, OpenAI-compatible)
    - `OpenAIEmbedder` (OpenAI /v1/embeddings)
    - `NullEmbedder`  (raises, forces you to wire a real model)

No new hard dependency: uses urllib + os.environ for keys. In CI (no key)
the hashing embedder remains the default so tests stay green offline.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, List, Protocol, Sequence


class Embedder(Protocol):
    """(text, dim) -> normalized float vector. The VectorMemory contract."""
    dim: int
    def __call__(self, text: str, dim: int = ...) -> List[float]: ...


class _HttpEmbedder:
    """Shared OpenAI-compatible embeddings endpoint wrapper (stdlib HTTP)."""

    def __init__(self, api_key: str, endpoint: str,
                 model: str, dim: int = 256, timeout: int = 30) -> None:
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.dim = dim
        self.timeout = timeout

    def __call__(self, text: str, dim: int | None = None) -> List[float]:
        dim = dim or self.dim
        body = json.dumps({"model": self.model, "input": text,
                           "dimensions": dim}).encode()
        req = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            })
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        vec = data["data"][0]["embedding"]
        if len(vec) != dim:
            vec = vec[:dim] if len(vec) > dim else vec + [0.0] * (dim - len(vec))
        # L2-normalize
        import math
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        return [self(t) for t in texts]


def AgnesEmbedder(api_key: str | None = None,
                  endpoint: str | None = None,
                  model: str = "agnes-embed",
                  dim: int = 256) -> _HttpEmbedder:
    """Agnes AI embeddings (OpenAI-compatible /api/embeddings)."""
    api_key = api_key or os.environ.get("AGNES_API_KEY")
    endpoint = endpoint or os.environ.get(
        "AGNES_EMBED_ENDPOINT", "https://apihub.agnes-ai.com/v1/embeddings")
    if not api_key:
        raise ValueError("AGNES_API_KEY required (env) or pass api_key=")
    return _HttpEmbedder(api_key, endpoint, model, dim)


def OpenAIEmbedder(api_key: str | None = None,
                   model: str = "text-embedding-3-small",
                   dim: int = 256) -> _HttpEmbedder:
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY required (env) or pass api_key=")
    return _HttpEmbedder(api_key, "https://api.openai.com/v1/embeddings",
                         model, dim)


class NullEmbedder:
    """Placeholder: raises so you can't silently run without a real model."""
    dim = 256

    def __init__(self) -> None:
        self._dim = 256

    @property
    def dim(self) -> int:
        return self._dim

    def __call__(self, text: str, dim: int | None = None) -> List[float]:
        raise RuntimeError(
            "NullEmbedder has no backend - wire AgnesEmbedder/OpenAIEmbedder "
            "or use charter.vector_memory.hash_embed for offline recall")


def pick_embedder(provider: str = "auto", **kw) -> Any:
    """Resolve an embedder by provider name; 'auto' prefers Agnes if key set.

    For 'openai' and 'agnes', the corresponding *_API_KEY env var (or an
    explicit api_key= kwarg) is required; otherwise ValueError is raised.
    A stray GITHUB_TOKEN or other generic token does NOT satisfy the check.
    """
    p = provider.lower()
    if p == "agnes" or (p == "auto" and os.environ.get("AGNES_API_KEY")):
        return AgnesEmbedder(**kw.get("agnes", {}))
    if p == "openai":
        # Strict check: only OPENAI_API_KEY (or explicit api_key=) is accepted.
        # GITHUB_TOKEN / AGNES_API_KEY / other env vars are deliberately ignored
        # so that CI environments that always have GITHUB_TOKEN set still
        # correctly raise when no real OPENAI_API_KEY is present.
        api_key = kw.get("openai", {}).get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY required (env) or pass pick_embedder("
                "'openai', openai={'api_key': '...'})"
            )
        return OpenAIEmbedder(**kw.get("openai", {}))
    if p == "null":
        return NullEmbedder()
    raise KeyError(f"unknown embedder provider {provider!r}")
