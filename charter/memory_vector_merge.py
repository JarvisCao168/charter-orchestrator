"""Cross-language memory merging in true vector space (v2.10).

Lifts `charter/memory_cross_language.py` (keyword-table + Jaccard merging)
to **embedding-space** merging: episodes / clusters are embedded with a
real embedder (a multilingual-capable LLM embedder when a key is set, or
the offline hashing embedder otherwise), and clusters merge when their
*centroid vectors* are close - a language-agnostic signal that catches
same-topic cross-language pairs even when the keyword table has no entry.

    - `VectorMergedCluster` - a merged result with the member clusters,
      their languages, a combined centroid, and a size.
    - `embed_clusters(clusters, embed, dim)` - embed each cluster's
      representative text -> a centroid vector per cluster.
    - `vector_cross_merge(embedded, similarity)` - agglomerative merge of
      clusters whose centroid cosine >= `similarity`, regardless of
      language.
    - `merge_in_vector_space(episodes, embed, ...)` - one-shot: embed +
      cluster (via `charter.memory_clustering`) + vector cross-merge,
      returning the merged set + a report.

The embedder is pluggable through `charter.embed_cache.production_embedder`:
    - `which="agnes"` / `"openai"` with a key -> a multilingual LLM
      embedding (the "true vector space" the candidate asked for).
    - no key -> the offline hashing embedder (still a real vector space,
      just language-agnostic n-gram features) so the merge runs in CI.

Stdlib-only. The merge is pure vector math; the only "true" dependency is
the embedder, which is optional.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .memory_clustering import MemoryClusterer, cluster_episodes
from .embed_cache import production_embedder
from .vector_memory import hash_embed, DIM

__all__ = [
    "VectorMergedCluster", "embed_clusters", "vector_cross_merge",
    "merge_in_vector_space",
]


@dataclass
class VectorMergedCluster:
    topic: str
    languages: List[str]
    member_ids: List[int]
    centroid: List[float]
    size: int
    cross_language: bool = False
    merged_from: int = 1

    def as_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic, "languages": self.languages,
            "member_ids": self.member_ids, "size": self.size,
            "cross_language": self.cross_language,
            "merged_from": self.merged_from,
            "centroid_dim": len(self.centroid),
        }


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def embed_clusters(
        clusters: List[Dict[str, Any]],
        embed: Optional[Callable[[str, int], List[float]]] = None,
        dim: int = DIM,
        which: Optional[str] = None,
        ) -> List[Dict[str, Any]]:
    """Embed each cluster's representative text -> a centroid vector.

    `clusters` is a `cluster_episodes` result (dicts with `top_content`).
    Returns the same list with `centroid` + `centroid_sim` keys attached.
    When no `embed` is given, `which` selects the embedder (default: the
    offline hashing embedder, so this works in CI; pass a multilingual
    LLM embedder for a true cross-lingual space).
    """
    emb = embed or production_embedder(which=which,
                                       disk_cache=False).__call__
    for c in clusters:
        rep = c.get("top_content", "") or c.get("label", "")
        c["centroid"] = emb(rep, dim)
    return clusters


def vector_cross_merge(
        embedded: List[Dict[str, Any]],
        similarity: float = 0.82,
        max_merged: int = 40,
        ) -> List[VectorMergedCluster]:
    """Agglomerative merge of clusters whose centroid cosine >= `similarity`,
    regardless of language. A cluster that merges across two or more
    distinct languages is flagged `cross_language=True`."""
    if not embedded:
        return []
    clusters: List[VectorMergedCluster] = []
    used = set()
    # seed with the largest clusters first (stable representative)
    order = sorted(range(len(embedded)),
                   key=lambda i: -embedded[i].get("size", 1))
    for i in order:
        if i in used:
            continue
        c = embedded[i]
        m = VectorMergedCluster(
            topic=(c.get("top_content", "") or c.get("label", "misc"))[:40],
            languages=[c.get("language", "und")]
            if c.get("language") else [],
            member_ids=list(c.get("member_ids", [])),
            centroid=list(c["centroid"]),
            size=c.get("size", 1),
            cross_language=False,
            merged_from=1,
        )
        for j in order:
            if j == i or j in used:
                continue
            cj = embedded[j]
            if _cosine(c["centroid"], cj["centroid"]) >= similarity:
                used.add(j)
                m.member_ids.extend(cj.get("member_ids", []))
                m.size += cj.get("size", 1)
                m.merged_from += 1
                lang_j = cj.get("language", "und")
                if lang_j not in m.languages:
                    m.languages.append(lang_j)
                if len(m.languages) > 1:
                    m.cross_language = True
                # recompute centroid as the mean of the root + merged members
                members = [i] + [j for j in used if j != i]
                m.centroid = _mean_vector(
                    [embedded[k]["centroid"] for k in members],
                    len(m.centroid))
        used.add(i)
        clusters.append(m)
    clusters = clusters[:max_merged]
    clusters.sort(key=lambda m: -m.size)
    return clusters


def _mean_vector(vectors: List[Sequence[float]],
                 dim: int) -> List[float]:
    if not vectors:
        return [0.0] * dim
    n = len(vectors)
    out = [0.0] * dim
    for v in vectors:
        for k in range(min(dim, len(v))):
            out[k] += v[k] / n
    return out


def merge_in_vector_space(
        episodes: List[Dict[str, Any]],
        similarity: float = 0.62,
        max_clusters: int = 30,
        cross_sim: float = 0.82,
        embed: Optional[Callable[[str, int], List[float]]] = None,
        which: Optional[str] = None,
        dim: int = DIM,
        ) -> Dict[str, Any]:
    """tool: merge_in_vector_space - embed + cluster + vector cross-merge.

    `which` selects the embedder: a multilingual LLM embedder ("agnes" /
    "openai" with a key) gives a true cross-lingual vector space; no key
    falls back to the offline hashing embedder (a real vector space, but
    n-gram-based). Returns {episodes, raw_clusters, merged_clusters,
    cross_language, report, merged}.
    """
    cl = MemoryClusterer(embed=embed or production_embedder(
        which=which, disk_cache=False).__call__,
        similarity=similarity, max_clusters=max_clusters)
    clusters = cl.cluster(episodes)
    # build cluster dicts with a language tag + representative text
    cluster_dicts: List[Dict[str, Any]] = []
    for idx, c in enumerate(clusters):
        rep = c.top_content or c.label
        d = c.as_dict()
        d["language"] = _guess_language(rep)
        d["top_content"] = rep
        cluster_dicts.append(d)
    embedded = embed_clusters(cluster_dicts, embed=embed, dim=dim,
                              which=which)
    merged = vector_cross_merge(embedded, similarity=cross_sim)
    cross = [m for m in merged if m.cross_language]
    return {
        "episodes": len(episodes),
        "raw_clusters": len(cluster_dicts),
        "merged_clusters": len(merged),
        "cross_language": len(cross),
        "report": (f"{len(episodes)} episodes -> {len(cluster_dicts)} "
                   f"clusters -> {len(merged)} vector-merged "
                   f"({len(cross)} cross-language)"),
        "embedder": "llm" if (which in ("agnes", "openai")) else "hashing",
        "merged": [m.as_dict() for m in merged],
    }


def _guess_language(text: str) -> str:
    """A tiny language guess (CJK -> zh, kana -> ja, hangul -> ko,
    otherwise -> en/und). Reused from the keyword-based detector's
    script logic (no external NLP dep)."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    total = max(1, len([ch for ch in text if ch.isalnum()]))
    if cjk > 0.4 * total:
        return "zh"
    if sum(1 for ch in text if "\u3040" <= ch <= "\u30ff") > 0.15 * total:
        return "ja"
    if sum(1 for ch in text if "\uac00" <= ch <= "\ud7af") > 0.2 * total:
        return "ko"
    return "en" if any(ch.isascii() and ch.isalpha() for ch in text) \
        else "und"
