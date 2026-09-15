"""LLM auto-naming for memory clusters (v2.7).

Lifts `charter/memory_clustering.py` (clustering with a heuristic label
derived from the first 4 words of a representative episode) to a **named**
corpus: after `cluster_episodes` groups the episodes, this module asks an
LLM (or a deterministic fallback) for a *short, human-readable name* + a
one-line description per cluster, based on the cluster's members.

    - `ClusterNamer` - protocol: `(members) -> {name, description}`
    - `LLMClusterNamer` - Agnes/OpenAI: "Given these memory episodes, return
      a 1-3 word name + a one-line description for the cluster. JSON only."
    - `HeuristicClusterNamer` - offline: name = top 2 content words,
      description = "N episodes about <top words>"
    - `name_clusters(clusters, embed?, which?)` - run the namer over a list
      of `Cluster` dicts (from `cluster_episodes`), attaching
      `name` + `description` to each.
    - `named_cluster_report(...)` - one-shot: cluster + name + store the
      named summaries back into a SessionStore.

Stdlib-only. Pluggable like `pr_sentiment`: a key enables the LLM namer,
otherwise the heuristic namer. `name_clusters` never raises on a per-cluster
LLM failure (it degrades that one cluster to the heuristic name).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence

__all__ = [
    "ClusterNamer", "HeuristicClusterNamer", "LLMClusterNamer",
    "name_clusters", "named_cluster_report", "pick_namer",
]


class ClusterNamer(Protocol):
    analyzer: str
    def name(self, members: List[str]) -> Dict[str, str]:
        """-> {"name": str, "description": str}"""
        ...


_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "it", "its", "this", "that", "in", "on", "at", "to", "of", "for",
    "with", "by", "from", "as", "be", "been", "do", "did", "we", "you",
    "they", "i", "me", "my", "your", "our", "their", "will", "would",
    "could", "should", "can", "may", "might", "not", "no", "yes", "if",
    "then", "than", "so", "such", "each", "every", "all", "any",
}


def _content_words(text: str) -> List[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower())
    return [w for w in words if w not in _STOPWORDS]


class HeuristicClusterNamer:
    """Offline deterministic cluster naming (top content words)."""

    name = "heuristic"

    def name_cluster(self, members: List[str]) -> Dict[str, str]:
        from collections import Counter
        counter: Counter = Counter()
        for m in members:
            counter.update(_content_words(m))
        top = [w for w, _ in counter.most_common(3)]
        if not top:
            return {"name": "misc", "description": f"{len(members)} episodes"}
        cluster_name = "-".join(top[:2])[:24] or "misc"
        desc = (f"{len(members)} episodes about " +
                ", ".join(top[:4]))
        return {"name": cluster_name, "description": desc[:140]}


class LLMClusterNamer:
    """Real LLM cluster namer (Agnes/OpenAI)."""

    name = "llm"

    def __init__(self, api_key: str, model: str, base_url: str,
                 timeout: int = 40) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def name(self, members: List[str]) -> Dict[str, str]:
        sys_prompt = (
            "Given a list of memory-episode texts, return a short cluster "
            "name (1-3 words, kebab-case) and a one-line description. "
            "Respond ONLY with JSON: {\"name\": \"...\", "
            "\"description\": \"...\"}. No prose outside the JSON."
        )
        blob = json.dumps(members[:24], ensure_ascii=False)
        if len(blob) > 6000:
            blob = blob[:6000] + "...(truncated)"
        user_prompt = f"Episodes:\n{blob}\n\nReturn the JSON now."
        body = json.dumps({
            "model": self.model, "temperature": 0.0,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        s = content.find("{")
        e = content.rfind("}")
        if s != -1 and e != -1 and e > s:
            content = content[s:e + 1]
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = {}
        name = str(raw.get("name", "misc")).strip()[:32] or "misc"
        desc = str(raw.get("description", "")).strip()[:200]
        return {"name": name, "description": desc}


def pick_namer(backend: Optional[str] = None,
               api_key: Optional[str] = None) -> ClusterNamer:
    """Pick a namer. None auto-detects: key -> llm, else heuristic."""
    backend = backend or os.environ.get("CLUSTER_NAMER")
    if backend is None:
        if api_key or os.environ.get("AGNES_API_KEY") or \
           os.environ.get("OPENAI_API_KEY"):
            backend = "llm"
        else:
            backend = "heuristic"
    if backend == "heuristic":
        return HeuristicClusterNamer()
    if backend == "llm":
        key = api_key or os.environ.get("AGNES_API_KEY") or \
            os.environ.get("OPENAI_API_KEY") or ""
        model = os.environ.get("AGNES_MODEL", "agnes-2.5-flash")
        base_url = os.environ.get(
            "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
        return LLMClusterNamer(key, model, base_url)
    raise ValueError(f"unknown namer backend: {backend!r}")


def name_clusters(clusters: List[Dict[str, Any]],
                  backend: Optional[str] = None,
                  api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """tool: name_clusters - attach a name + description to each cluster.

    `clusters` is the output of `charter.memory_clustering.cluster_episodes`
    (a list of dicts with `label` / `top_content` / `size` / `member_ids`).
    Returns the same list with `name` + `description` added (and `naming`
    = the analyzer name). Per-cluster LLM failures degrade to the
    heuristic namer for that cluster only.
    """
    namer = pick_namer(backend, api_key)
    fallback = HeuristicClusterNamer()
    out: List[Dict[str, Any]] = []
    for c in clusters:
        members: List[str] = []
        # gather member content from top_content (the representative) plus
        # any stored member previews; the clustering step only kept
        # top_content, so we name from that + the label.
        preview = c.get("top_content", "") or c.get("label", "")
        members = [preview]
        try:
            named = namer.name_cluster(members)
            out.append({**c, "name": named["name"],
                        "description": named["description"],
                        "naming": namer.name})
        except Exception:
            named = fallback.name_cluster(members)
            out.append({**c, "name": named["name"],
                        "description": named["description"],
                        "naming": "heuristic-fallback"})
    return out


def named_cluster_report(store, session_id: str, agent_id: str,
                         similarity: float = 0.62,
                         max_clusters: int = 12,
                         backend: Optional[str] = None,
                         api_key: Optional[str] = None,
                         which: Optional[str] = None,
                         salience: float = 2.5,
                         ) -> Dict[str, Any]:
    """tool: named_cluster_report - cluster + name a session's episodes,
    store the *named* cluster summaries back into the store.

    Returns {session_id, episodes, clusters, reduction, stored,
    named_clusters:[{name, description, size, top_content}]}.
    """
    from .memory_clustering import cluster_episodes
    eps = store.recall(agent_id, "all", session_id=session_id, limit=500)
    raw = [e for e in eps if e.get("kind") not in
           ("cluster_summary", "named_cluster")]
    raw = raw or eps
    eps_dicts = [{"id": i, "content": e.get("content", ""),
                   "salience": e.get("salience", 1.0)}
                  for i, e in enumerate(raw)]
    clusters = cluster_episodes(eps_dicts, similarity=similarity,
                                 max_clusters=max_clusters, which=which)
    named = name_clusters(clusters, backend=backend, api_key=api_key)
    stored = 0
    for nc in named:
        text = (f"[{nc.get('name', 'misc')}] "
                f"({nc['size']} episodes): {nc.get('description', '')}")
        store.remember(session_id, agent_id, text,
                        kind="named_cluster", salience=salience)
        stored += 1
    return {
        "session_id": session_id,
        "episodes": len(raw),
        "clusters": len(named),
        "reduction": len(raw) / max(1, len(named)),
        "stored": stored,
        "named_clusters": [
            {"name": nc.get("name"), "description": nc.get("description"),
             "size": nc["size"], "top_content": nc.get("top_content", ""),
             "naming": nc.get("naming")}
            for nc in named],
    }
