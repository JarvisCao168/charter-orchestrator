"""Cross-language automatic merging of memory clusters (v2.9).

Lifts `charter/cluster_multilingual.py` (names each cluster in its
detected language, independently) to **cross-language merging**: two
clusters that talk about the *same underlying topic* in *different
languages* are detected and merged into one, so a multilingual
memory store doesn't keep "数据库连接池调优" (zh) and "database
connection pool tuning" (en) as two separate clusters.

    - `detect_topic_keywords(text, lang)` - the topic-bearing keywords of
      an episode, transliterated to a common (Latin) form so cross-language
      matching can happen. Uses a small built-in CJK -> pinyin/roman
      table for the common technical terms (database, connection, pool,
      auth, token, deploy, test, cache, ...).
    - `cross_language_merge(clusters, similarity=...)` - merge two
      clusters when their keyword sets overlap (Jaccard) *or* their
      embedding centroids are similar *and* they are in different
      languages.
    - `MergedCluster` - the merged result: {language, merged_languages,
      name, description, member_ids, topic, size}.
    - `merge_cross_language(episodes, ...)` - one-shot: embed + cluster
      (via `charter.memory_clustering`) then merge across languages,
      returning the merged set + a report.

Stdlib-only. The keyword transliteration table is small (enough for the
common agent-memory technical vocabulary); an LLM is NOT required, so
this works offline in CI.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .memory_clustering import MemoryClusterer, cluster_episodes
from .cluster_multilingual import detect_language
from .embed_cache import production_embedder
from .vector_memory import hash_embed, DIM

__all__ = [
    "MergedCluster", "detect_topic_keywords", "cross_language_merge",
    "merge_cross_language",
]

# A small CJK technical-term -> roman keyword map. Enough to let a zh
# "数据库连接池" cluster merge with an en "database connection pool"
# cluster (both -> {database, connection, pool}).
_CJK_KEYWORDS: Dict[str, List[str]] = {
    "数据库": ["database"], "连接池": ["connection", "pool"],
    "连接": ["connection"], "池": ["pool"], "调优": ["tuning"],
    "认证": ["auth", "authentication"], "登录": ["login", "auth"],
    "令牌": ["token"], "部署": ["deploy", "deployment"],
    "迁移": ["migration"], "测试": ["test"], "缓存": ["cache"],
    "网关": ["gateway"], "路由": ["routing"], "审计": ["audit"],
    "日志": ["log"], "配置": ["config"], "密钥": ["key", "secret"],
    "会话": ["session"], "并发": ["concurrency"], "限流": ["throttle"],
}

# en technical keywords (already Latin)
_EN_KEYWORDS = [
    "database", "db", "connection", "pool", "tune", "tuning", "auth",
    "authentication", "login", "token", "jwt", "deploy", "deployment",
    "migration", "test", "cache", "gateway", "routing", "audit", "log",
    "config", "key", "secret", "session", "concurrency", "throttle",
    "checkpoint", "gate", "stage", "artifact", "governance", "agent",
]


def detect_topic_keywords(text: str, lang: str) -> List[str]:
    """tool: detect_topic_keywords - the topic keywords of an episode, in a
    common (Latin) form so cross-language matching works.

    For CJK, the built-in table maps the detected technical terms to
    roman keywords; for Latin scripts the content words are kept. Returns
    a sorted, deduped keyword list (lower-cased).
    """
    text = (text or "").strip()
    lang = (lang or detect_language(text)).lower()
    kws: List[str] = []
    if lang in ("zh", "ja", "ko"):
        # scan the CJK keyword table against the text
        for cjk, romans in _CJK_KEYWORDS.items():
            if cjk in text:
                kws.extend(romans)
        # also pick up any Latin words embedded (e.g. "Postgres" in a
        # CJK sentence)
        kws.extend(re.findall(r"[A-Za-z]{3,}", text))
    else:
        # Latin: keep content words (drop stopwords via a small set)
        stop = {"the", "a", "an", "and", "or", "but", "is", "are",
                "was", "were", "it", "its", "this", "that", "in", "on",
                "at", "to", "of", "for", "with", "by", "from", "as",
                "be", "been", "do", "we", "you", "they", "i", "me",
                "my", "your", "our", "their", "will", "would", "could",
                "should", "can", "may", "might", "not", "no", "if",
                "then", "so", "each", "all", "any"}
        for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text.lower()):
            if w not in stop and w in _EN_KEYWORDS:
                kws.append(w)
        # also keep the top content words even if not in the known set
        seen = set(kws)
        for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text.lower()):
            if w not in stop and w not in seen and len(w) > 3:
                kws.append(w)
                seen.add(w)
    # dedupe + sort
    return sorted(set(k.lower() for k in kws))


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


@dataclass
class MergedCluster:
    topic: str
    languages: List[str]
    language: str            # the primary (first-seen) language
    name: str
    description: str
    member_ids: List[int]
    size: int
    merged: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic, "language": self.language,
            "languages": self.languages, "name": self.name,
            "description": self.description, "member_ids": self.member_ids,
            "size": self.size, "merged": self.merged,
        }


def cross_language_merge(clusters: List[Dict[str, Any]],
                         keyword_sets: Dict[str, List[str]],
                         similarity: float = 0.34,
                         ) -> List[MergedCluster]:
    """Merge clusters that share topic keywords OR similar centroids across
    different languages. `clusters` is a `cluster_episodes` result;
    `keyword_sets` maps a cluster-key -> its topic keywords.

    A merge happens when two clusters are in *different* languages and
    their keyword Jaccard >= `similarity` (or centroid cosine >= 0.85 when
    a `centroid` key is present).
    """
    merged: List[MergedCluster] = []
    used = set()
    # order: larger clusters first so the merge representative is stable
    ordered = sorted(
        range(len(clusters)),
        key=lambda i: -clusters[i].get("size", 1))
    for i in ordered:
        if i in used:
            continue
        c = clusters[i]
        ki = keyword_sets.get(str(i), [])
        lang_i = c.get("language", "")
        m = MergedCluster(
            topic=ki[0] if ki else "misc",
            language=lang_i,
            languages=[lang_i] if lang_i else [],
            name=c.get("name", c.get("label", "misc")),
            description=c.get("description", ""),
            member_ids=list(c.get("member_ids", [])),
            size=c.get("size", len(c.get("member_ids", []))),
            merged=False,
        )
        for j in ordered:
            if j == i or j in used:
                continue
            cj = clusters[j]
            kj = keyword_sets.get(str(j), [])
            lang_j = cj.get("language", "")
            if lang_j == lang_i:
                continue  # same language -> not a *cross-language* merge
            jac = _jaccard(ki, kj)
            cos = 0.0
            if "centroid" in c and "centroid" in cj:
                cos = _cosine(c["centroid"], cj["centroid"])
            if jac >= similarity or cos >= 0.85:
                m.languages.append(lang_j)
                m.member_ids.extend(cj.get("member_ids", []))
                m.size += cj.get("size", len(cj.get("member_ids", [])))
                m.merged = True
                # fold j's keywords in (topic = top shared keyword)
                shared = [w for w in ki if w in kj]
                if shared:
                    m.topic = shared[0]
                elif kj:
                    m.topic = kj[0]
                used.add(j)
        used.add(i)
        merged.append(m)
    # order by size desc
    merged.sort(key=lambda m: -m.size)
    return merged


def merge_cross_language(
        episodes: List[Dict[str, Any]],
        similarity: float = 0.62,
        max_clusters: int = 30,
        cross_sim: float = 0.34,
        embed: Optional[Callable[[str, int], List[float]]] = None,
        which: Optional[str] = None) -> Dict[str, Any]:
    """tool: merge_cross_language - embed + cluster, then merge across
    languages.

    Returns {episodes, raw_clusters, merged_clusters,
    merged_by_language, report}. `merged_by_language` counts how many
    merged clusters span 2+ languages; `report` is a short digest.
    """
    emb = embed or production_embedder(which=which,
                                       disk_cache=False).__call__
    cl = MemoryClusterer(embed=emb, similarity=similarity,
                         max_clusters=max_clusters)
    clusters = cl.cluster(episodes)
    # MemoryClusterer returns Cluster dataclass objects; convert to the
    # dict shape that cross_language_merge + detect expect.
    cluster_dicts: List[Dict[str, Any]] = []
    keyword_sets: Dict[str, List[str]] = {}
    for idx, cc in enumerate(clusters):
        rep = cc.top_content or cc.label
        lang = detect_language(rep)
        d = cc.as_dict()
        d["language"] = lang
        d["centroid"] = emb(rep, getattr(cl, "dim", DIM))
        d["name"] = d.get("label", "cluster-" + str(idx))
        d["description"] = f"{d.get('size', 1)} episodes about {rep[:80]}"
        cluster_dicts.append(d)
        keyword_sets[str(idx)] = detect_topic_keywords(rep, lang)
    merged = cross_language_merge(cluster_dicts, keyword_sets,
                                  similarity=cross_sim)
    multi = [m for m in merged if len(m.languages) > 1]
    return {
        "episodes": len(episodes),
        "raw_clusters": len(clusters),
        "merged_clusters": len(merged),
        "merged_by_language": len(multi),
        "report": (f"{len(episodes)} episodes -> {len(clusters)} raw "
                   f"clusters -> {len(merged)} merged "
                   f"({len(multi)} cross-language)"),
        "merged": [m.as_dict() for m in merged],
    }
