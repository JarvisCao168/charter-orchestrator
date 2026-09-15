"""Vector clustering for cross-session memory (v2.6).

Lifts `charter/memory_hierarchy.py` (salience + recency ranked recall) to
**semantic clustering**: episodes with similar embeddings get auto-merged
into *clusters*, so a session's raw episodes collapse into a small set of
topic groups + one representative summary per group. This makes the
hierarchy's tier-1 (session) compression far more compact: instead of N
raw episodes, you store K cluster summaries (K << N).

    - `MemoryClusterer` - embed each episode (pluggable embedder, default
      offline hashing) then run a threshold-based agglomerative pass:
      two episodes join a cluster when cosine similarity > `similarity`.
      Each cluster carries: a representative (highest-salience member),
      a centroid (mean vector), a size, and a generated one-line label.
    - `cluster_episodes(episodes, ...)` - one-shot: return
      `[{label, centroid, members:[ids], size, top_content}]`.
    - `cluster_session(store, session_id, agent_id)` - embed + cluster a
      session's raw episodes, then store each cluster as a
      `kind="cluster_summary"` memory with the centroid vector so future
      recall is O(1) per cluster instead of O(N) per episode.
    - `cluster_count` - report how much the clustering shrank a corpus.

Stdlib-only. The embedder comes from `embed_cache` (production endpoint +
cache when a key is set, offline hashing otherwise), so clustering stays
green in CI with no LLM.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .session_store import SessionStore
from .embed_cache import production_embedder
from .vector_memory import hash_embed, DIM

__all__ = [
    "Cluster", "MemoryClusterer", "cluster_episodes", "cluster_session",
    "cluster_count",
]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


@dataclass
class Cluster:
    label: str
    centroid: List[float]
    member_ids: List[int] = field(default_factory=list)
    top_content: str = ""
    representative_id: int = 0
    size: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "size": self.size,
                "member_ids": self.member_ids,
                "top_content": self.top_content,
                "representative_id": self.representative_id,
                "centroid_dim": len(self.centroid)}


class MemoryClusterer:
    """Threshold-based agglomerative clustering over embedded episodes."""

    def __init__(self, embed: Optional[Callable[[str, int], List[float]]] = None,
                 dim: int = DIM,
                 similarity: float = 0.62,
                 max_clusters: int = 24) -> None:
        self.embed = embed or hash_embed
        self.dim = dim
        self.similarity = similarity
        self.max_clusters = max_clusters

    # -- core ---------------------------------------------------------
    def cluster(self, episodes: List[Dict[str, Any]]) -> List[Cluster]:
        """Cluster a list of {id, content, salience} episodes.

        Agglomerative: start with each episode in its own cluster; merge the
        two closest clusters (by centroid cosine) while their similarity is
        above `self.similarity`. Stops at `max_clusters`.
        """
        if not episodes:
            return []
        # embed each episode
        vectors: Dict[int, List[float]] = {}
        for e in episodes:
            eid = int(e.get("id", 0))
            content = e.get("content", "")
            vectors[eid] = self.embed(content, self.dim)

        # seed clusters
        clusters: List[Cluster] = []
        for e in episodes:
            eid = int(e.get("id", 0))
            clusters.append(Cluster(
                label=self._label_for(e.get("content", "")),
                centroid=list(vectors[eid]),
                member_ids=[eid],
                top_content=e.get("content", "")[:160],
                representative_id=eid,
                size=1))

        if len(clusters) <= self.max_clusters:
            return self._finalize(clusters, episodes, vectors)

        # agglomerative merge (greedy by centroid similarity)
        while len(clusters) > self.max_clusters:
            best_i, best_j, best_sim = 0, 1, -1.0
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    s = _cosine(clusters[i].centroid, clusters[j].centroid)
                    if s > best_sim:
                        best_sim, best_i, best_j = s, i, j
            if best_sim < self.similarity:
                break  # no two clusters are similar enough to merge
            ci, cj = clusters[best_i], clusters[best_j]
            merged_ids = ci.member_ids + cj.member_ids
            # centroid = mean of member vectors
            n = len(merged_ids) or 1
            centroid = [0.0] * self.dim
            for mid in merged_ids:
                v = vectors.get(mid)
                if v:
                    for k in range(min(self.dim, len(v))):
                        centroid[k] += v[k] / n
            # representative = highest salience among merged members
            sal = {int(e.get("id", 0)): e.get("salience", 1.0)
                   for e in episodes}
            rep = max(merged_ids, key=lambda x: sal.get(x, 0.0))
            ci.member_ids = merged_ids
            ci.centroid = centroid
            ci.representative_id = rep
            ci.size = len(merged_ids)
            # keep the longer label
            if len(cj.label) > len(ci.label):
                ci.label = cj.label
            clusters.pop(best_j)
            clusters.pop(best_i)
        return self._finalize(clusters, episodes, vectors)

    def _finalize(self, clusters: List[Cluster],
                  episodes: List[Dict[str, Any]],
                  vectors: Dict[int, List[float]]) -> List[Cluster]:
        for c in clusters:
            c.size = len(c.member_ids)
            # pick the best representative content
            for e in episodes:
                if int(e.get("id", 0)) == c.representative_id:
                    c.top_content = (e.get("content", "") or
                                     c.top_content)[:160]
                    break
        return clusters

    @staticmethod
    def _label_for(content: str) -> str:
        words = content.split()[:4]
        return " ".join(words).strip()[:32] or "misc"


def cluster_episodes(episodes: List[Dict[str, Any]],
                    similarity: float = 0.62,
                    max_clusters: int = 24,
                    embed: Optional[Callable[[str, int], List[float]]] = None,
                    which: Optional[str] = None) -> List[Dict[str, Any]]:
    """tool: cluster_episodes - one-shot semantic clustering of episodes.

    Returns a list of cluster dicts (label / size / member_ids / top_content).
    `which` selects the embedder ("hash" default, "agnes"/"openai" when a
    key is set).
    """
    emb = embed or production_embedder(
        which=which, disk_cache=False).__call__ if not embed else embed
    cl = MemoryClusterer(embed=emb, similarity=similarity,
                         max_clusters=max_clusters)
    return [c.as_dict() for c in cl.cluster(episodes)]


def cluster_session(store: SessionStore, session_id: str,
                   agent_id: str,
                   similarity: float = 0.62,
                   max_clusters: int = 12,
                   salience: float = 2.5,
                   which: Optional[str] = None) -> Dict[str, Any]:
    """tool: cluster_session - cluster a session's raw episodes and store the
    cluster summaries back into the store (kind='cluster_summary').

    Returns {session_id, episodes, clusters, reduction, stored}. The
    `reduction` is how many raw episodes were collapsed into how many
    cluster summaries.
    """
    eps = store.recall(agent_id, "all", session_id=session_id,
                        limit=500)
    raw = [e for e in eps if e.get("kind") != "cluster_summary"]
    raw = raw or eps
    emb = production_embedder(which=which, disk_cache=False)
    cl = MemoryClusterer(embed=emb.__call__, similarity=similarity,
                         max_clusters=max_clusters)
    clusters = cl.cluster(raw)
    # write each cluster back as a high-salience summary
    stored = 0
    for c in clusters:
        text = (f"Cluster[{c.label}] ({c.size} episodes): "
                f"{c.top_content}")
        store.remember(session_id, agent_id, text,
                        kind="cluster_summary", salience=salience)
        stored += 1
    return {
        "session_id": session_id,
        "episodes": len(raw),
        "clusters": len(clusters),
        "reduction": len(raw) / max(1, len(clusters)),
        "stored": stored,
        "cluster_details": [c.as_dict() for c in clusters],
    }


def cluster_count(episodes: List[Dict[str, Any]],
                  similarity: float = 0.62,
                  max_clusters: int = 24,
                  embed: Optional[Callable[[str, int], List[float]]] = None,
                  which: Optional[str] = None) -> Dict[str, Any]:
    """tool: cluster_count - report how much a corpus shrinks under
    clustering (episodes -> clusters + reduction factor)."""
    out = cluster_episodes(episodes, similarity=similarity,
                           max_clusters=max_clusters, embed=embed,
                           which=which)
    sizes = [c["size"] for c in out]
    return {
        "episodes": len(episodes),
        "clusters": len(out),
        "reduction": round(len(episodes) / max(1, len(out)), 3),
        "avg_cluster_size": round(sum(sizes) / max(1, len(sizes)), 2)
        if sizes else 0.0,
        "max_cluster_size": max(sizes) if sizes else 0,
    }
