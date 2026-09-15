"""Multilingual auto-naming for memory clusters (v2.8).

Lifts `charter/cluster_naming.py` (single-language: the name is derived
from the top content words of the English representative episode) to a
**multilingual** namer that can:

    - detect the dominant language of a cluster's members,
    - produce a cluster name *in that language* (a short 1-3 word label
      that a reviewer of that language will recognise),
    - fall back to an English / transliterated label when the language is
      unknown or the LLM is unavailable.

The namer is pluggable:
    - `LLMMultilingualNamer` - a real LLM call that names the cluster in
      the detected language (uses the same OpenAI-compatible chat
      endpoint as `cluster_naming.LLMClusterNamer`).
    - `HeuristicMultilingualNamer` - offline: language detection via a
      small stopword/character-coverage heuristic + a transliterated /
      top-word label; no network, no key.

`detect_language(text)` - a lightweight, dependency-free detector (script +
stopword cues) covering a practical set (en/zh/ja/ko/de/es/fr/ru/ar/...).
Returns an ISO 639-1 code or "und" (undetermined).

`multilingual_name_clusters(clusters, ...)` - run the multilingual namer
over a `cluster_episodes` result, attaching `name`, `description`, and
`language` to each cluster.

Stdlib-only. A key enables the LLM path; otherwise the heuristic one.
Per-cluster LLM failure degrades that cluster to the heuristic name (never
raises).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

__all__ = [
    "detect_language", "MultilingualNamer", "HeuristicMultilingualNamer",
    "LLMMultilingualNamer", "multilingual_name_clusters",
    "pick_multilingual_namer",
]

# Small stopword sets per language (a few high-frequency words each) used
# as language cues. Enough to disambiguate the common cases without a
# heavy NLP dependency.
_SW: Dict[str, set] = {
    "zh": {"的", "了", "是", "在", "和", "我", "你", "他", "她", "这",
           "那", "有", "就", "不", "人", "都", "一", "上", "也", "很"},
    "ja": {"の", "に", "は", "を", "た", "る", "て", "し", "き", "す",
           "だ", "も", "が", "で", "と", "え", "こ"},
    "ko": {"이", "가", "을", "를", "는", "에", "과", "도", "의", "로"},
    "de": {"der", "die", "das", "und", "ist", "nicht", "ein", "eine",
           "den", "dem", "des", "mit", "sich", "auf", "für"},
    "es": {"el", "la", "los", "las", "es", "que", "de", "un", "una",
           "por", "para", "con", "sus", "pero", "como"},
    "fr": {"le", "la", "les", "et", "est", "pas", "une", "pour", "dans",
           "sur", "qui", "mais", "aussi", "avec"},
    "ru": {"и", "в", "не", "что", "на", "по", "ya", "это", "из", "но"},
    "ar": {"في", "من", "على", "هو", "هذه", "هذا", "مع", "و", "لا", "كان"},
    "en": {"the", "a", "an", "and", "is", "are", "was", "were", "to",
           "in", "on", "at", "for", "of", "with", "by", "it", "its"},
}


def _cjk_coverage(text: str) -> float:
    """Fraction of characters that are CJK (Han)."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    total = max(1, len([ch for ch in text if ch.isalnum()]))
    return cjk / total


def _hiragana_katakana(text: str) -> int:
    return sum(1 for ch in text
               if "\u3040" <= ch <= "\u30ff")  # hiragana + katakana


def _devanagari_or_arabic(text: str) -> int:
    return sum(1 for ch in text
               if "\u0600" <= ch <= "\u06ff")   # Arabic block


def detect_language(text: str) -> str:
    """tool: detect_language - lightweight, dependency-free language
    detection. Returns an ISO 639-1 code ("en","zh","ja","ko","de","es",
    "fr","ru","ar") or "und" when undetermined.

    Heuristic: script coverage (CJK -> zh, kana -> ja, hangul -> ko,
    Arabic -> ar) first; then Latin-alphabet stopword cues. This is a
    practical detector for the common agent-memory languages, not a
    full NLP model.
    """
    t = (text or "").strip()
    if not t:
        return "und"
    alpha = [ch for ch in t if ch.isalnum()]
    if not alpha:
        return "und"
    cjk = _cjk_coverage(t)
    if cjk > 0.4:
        return "zh"
    if _hiragana_katakana(t) > 0.15 * len(alpha):
        return "ja"
    hangul = sum(1 for ch in t if "\uac00" <= ch <= "\ud7af")
    if hangul > 0.2 * len(alpha):
        return "ko"
    if _devanagari_or_arabic(t) > 0.2 * len(alpha):
        return "ar"

    # Latin + Cyrillic: score by stopword overlap
    words = re.findall(r"[A-Za-zА-Яа-я]+", t.lower())
    best, best_hits = "und", 0
    for lang, sw in _SW.items():
        hits = sum(1 for w in words if w in sw)
        if hits > best_hits:
            best, best_hits = lang, hits
    if best_hits > 0:
        return best
    # No stopword cue. If the text is pure Latin (no CJK/kana/hangul/arabic
    # was caught above) default to "en" - the common agent-memory language.
    if any(ch.isascii() and ch.isalpha() for ch in t):
        return "en"
    return "und"


class MultilingualNamer(Protocol):
    name: str
    def name(self, members: List[str],
             language: str) -> Dict[str, str]:
        """-> {"name","description","language"}"""
        ...


class HeuristicMultilingualNamer:
    """Offline multilingual naming: top content words in the detected
    language + a short label."""

    name = "heuristic-multilingual"

    def name(self, members: List[str], language: str) -> Dict[str, str]:
        joined = " ".join(members)
        # pick the language (max coverage across members)
        lang = detect_language(joined)
        # label: first few content tokens of the representative member
        rep = members[0] if members else ""
        label = _short_label(rep, lang)
        desc = (f"{len(members)} episodes ({lang or 'und'}): "
                + rep[:100])
        return {"name": label, "description": desc, "language": lang}

    @staticmethod
    def _stop_for(lang: str) -> set:
        return _SW.get(lang, set())


def _short_label(text: str, lang: str) -> str:
    stop = _SW.get(lang, set())
    if lang in ("zh", "ja", "ko"):
        # for CJK, take the first few characters (no word boundary)
        tokens = [ch for ch in text if "\u4e00" <= ch <= "\u9fff"
                  or "\u3040" <= ch <= "\u30ff"
                  or "\uac00" <= ch <= "\ud7af"]
        return "".join(tokens[:8]) or "misc"
    words = [w for w in re.findall(r"[A-Za-z]+", text.lower())
             if w not in stop and len(w) > 2]
    return "-".join(words[:3])[:24] or "misc"


class LLMMultilingualNamer:
    """Real LLM multilingual namer (Agnes/OpenAI). Names the cluster in the
    detected / target language."""

    name = "llm-multilingual"

    def __init__(self, api_key: str, model: str, base_url: str,
                 timeout: int = 40) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def name(self, members: List[str],
             language: str) -> Dict[str, Any]:
        lang_hint = language if language in _SW else detect_language(
            " ".join(members))
        target = lang_hint if lang_hint in _SW else "the language of the episodes"
        sys_prompt = (
            "Name this cluster of memory episodes in " + target +
            ". Return ONLY JSON: "
            '{"name": "<1-3 word label in that language>", '
            '"description": "<one line in that language>", '
            '"language": "<iso 639-1>"}'
        )
        blob = json.dumps(members[:24], ensure_ascii=False)
        if len(blob) > 6000:
            blob = blob[:6000] + "...(truncated)"
        user = f"Episodes:\n{blob}\n\nReturn the JSON now."
        body = json.dumps({
            "model": self.model, "temperature": 0.0,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user},
            ],
        }).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"].strip()
        s, e = content.find("{"), content.rfind("}")
        if s != -1 and e != -1 and e > s:
            content = content[s:e + 1]
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = {}
        return {
            "name": str(raw.get("name", "misc")).strip()[:32] or "misc",
            "description": str(raw.get("description",
                                       " ".join(members)[:120])).strip(),
            "language": str(raw.get("language",
                                     lang_hint))[:5],
        }


def pick_multilingual_namer(backend: Optional[str] = None,
                            api_key: Optional[str] = None
                            ) -> MultilingualNamer:
    """Pick a multilingual namer. None auto-detects: key -> llm, else
    heuristic."""
    backend = backend or os.environ.get("CLUSTER_MULTILINGUAL_NAMER")
    if backend is None:
        if api_key or os.environ.get("AGNES_API_KEY") or \
           os.environ.get("OPENAI_API_KEY"):
            backend = "llm"
        else:
            backend = "heuristic"
    if backend == "heuristic":
        return HeuristicMultilingualNamer()
    if backend == "llm":
        key = api_key or os.environ.get("AGNES_API_KEY") or \
            os.environ.get("OPENAI_API_KEY") or ""
        model = os.environ.get("AGNES_MODEL", "agnes-2.5-flash")
        base_url = os.environ.get(
            "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
        return LLMMultilingualNamer(key, model, base_url)
    raise ValueError(f"unknown multilingual namer backend: {backend!r}")


def multilingual_name_clusters(clusters: List[Dict[str, Any]],
                              backend: Optional[str] = None,
                              api_key: Optional[str] = None
                              ) -> List[Dict[str, Any]]:
    """tool: multilingual_name_clusters - name each cluster in its detected
    language, attaching `name` + `description` + `language`.

    `clusters` is the output of `charter.memory_clustering.cluster_episodes`
    (dicts with `label` / `top_content` / `size` / `member_ids`). Per-cluster
    LLM failures degrade to the heuristic namer for that cluster only.
    """
    namer = pick_multilingual_namer(backend, api_key)
    fallback = HeuristicMultilingualNamer()
    out: List[Dict[str, Any]] = []
    for c in clusters:
        members = [c.get("top_content", "") or c.get("label", "")]
        lang = detect_language(members[0]) if members else "und"
        try:
            named = namer.name(members, lang)
            out.append({**c, "name": named["name"],
                        "description": named["description"],
                        "language": named.get("language", lang),
                        "naming": namer.name})
        except Exception:
            named = fallback.name(members, lang)
            out.append({**c, "name": named["name"],
                        "description": named["description"],
                        "language": named.get("language", lang),
                        "naming": "heuristic-multilingual-fallback"})
    return out
