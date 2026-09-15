"""Cross-file + cross-hunk consistency for LLM PR diff completion (v2.9).

Lifts `charter/pr_diff_completion.py` (per-hunk completion in isolation)
to a **consistency** layer: when an LLM proposes code rewrites across
*hunks* and across *files*, those proposals can contradict each other
(a helper renamed in one hunk but not the next; a variable used before
it's defined across files). This module detects and reconciles those
inconsistencies so the reviewer gets a coherent patch set, not a bag of
independent rewrites.

    - `CrossHunkConsistency` - given a set of `HunkProposal`s, detect:
        * symbol renames that don't propagate (a symbol renamed in one
          hunk still appears under the old name in another),
        * a definition that a later hunk depends on but an earlier hunk
          removed,
        * conflicting `after` blocks on the *same* hunk id.
      Returns a report of inconsistencies + a set of `reconciled`
      proposals.
    - `reconcile_hunks(proposals)` - apply the reconciliation: for each
      inconsistency, patch the dependent hunk's `after` to match (rename
      propagation, re-introduce a removed symbol, pick the canonical
      `after` for a same-hunk conflict).
    - `cross_file_summary(proposals)` - a per-file digest of the
      proposals (which files / hunks changed, the cross-file symbol
      dependencies), so a reviewer can sanity-check the blast radius.

Stdlib-only. The symbol extraction is a lightweight heuristic (Python
identifiers + a rename-pair table built from the proposals' before/after
diffs), not a full LSP - enough to catch the common cross-hunk slip for
the agent's own code.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .pr_diff_completion import HunkProposal

__all__ = [
    "Inconsistency", "CrossHunkConsistency", "reconcile_hunks",
    "cross_file_summary",
]

_IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")


def _identifiers(code: str) -> Set[str]:
    return set(_IDENT.findall(code or ""))


@dataclass
class Inconsistency:
    kind: str            # "unpropagated-rename" | "removed-definition" | "conflicting-after"
    symbol: str
    hunk_ids: List[str]
    detail: str

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "symbol": self.symbol,
                "hunk_ids": self.hunk_ids, "detail": self.detail}


class CrossHunkConsistency:
    """Detect inconsistencies across a set of HunkProposals."""

    def __init__(self, proposals: List[HunkProposal]) -> None:
        self.proposals = proposals
        # hunk id -> (file, proposal)
        self._by_hunk: Dict[str, HunkProposal] = {}
        for p in proposals:
            self._by_hunk.setdefault(p.hunk_id, p)

    # -- extract symbol renames from a single hunk's before -> after ----
    def _renames(self, p: HunkProposal) -> Dict[str, str]:
        """{old_name: new_name} symbols renamed in this hunk.

        A 1:1 removed->added pair is treated as a rename regardless of
        string similarity (the common "rename one helper" case:
        get_data -> fetch_data). For 2+ removed / 2+ added, only pair
        symbols that share a prefix or stem to avoid pairing unrelated
        symbols.
        """
        before, after = _identifiers(p.before), _identifiers(p.after)
        removed = sorted(before - after)
        added = sorted(after - before)
        renames: Dict[str, str] = {}
        if len(removed) == 1 and len(added) == 1:
            # unambiguous 1:1 rename
            renames[removed[0]] = added[0]
        elif len(removed) >= 1 and len(added) >= 1:
            for old_sym in removed:
                for new_sym in added:
                    if old_sym[:4] == new_sym[:4] or \
                       old_sym[:-3] == new_sym[:-3]:
                        renames[old_sym] = new_sym
        return renames

    def detect(self) -> List[Inconsistency]:
        out: List[Inconsistency] = []
        # 1. unpropagated rename: a symbol renamed in hunk A still
        #    appears under the OLD name in hunk B (same file).
        rename_sources: Dict[str, str] = {}  # old -> new (global)
        for p in self.proposals:
            for old, new in self._renames(p).items():
                rename_sources.setdefault(old, new)
        for old, new in rename_sources.items():
            offenders: List[str] = []
            for p in self.proposals:
                # the OLD name still in this hunk's after -> unpropagated
                if re.search(rf"\b{re.escape(old)}\b", p.after):
                    offenders.append(p.hunk_id)
            if offenders:
                out.append(Inconsistency(
                    kind="unpropagated-rename", symbol=old,
                    hunk_ids=offenders,
                    detail=(f"'{old}' -> '{new}' renamed in one hunk but "
                            f"still referenced in {offenders}")))

        # 2. removed definition: a symbol is defined (assigned) in an
        #    earlier hunk's `before` but removed in its `after`, and a
        #    later hunk still *uses* it.
        defs: Set[str] = set()
        uses_after_removal: Dict[str, List[str]] = defaultdict(list)
        for p in self.proposals:
            b_ids = _identifiers(p.before)
            a_ids = _identifiers(p.after)
            removed_defs = b_ids - a_ids
            # a symbol "used" in a later hunk's after that was removed here
            for p2 in self.proposals:
                if p2 is p:
                    continue
                if re.search(rf"\b{re.escape('|'.join(removed_defs))}\b",
                              p2.after) if removed_defs else False:
                    pass
            # simpler: record per-hunk removed defs, then cross-check
            for sym in removed_defs:
                for p2 in self.proposals:
                    if p2 is not p and re.search(
                            rf"\b{re.escape(sym)}\b", p2.after):
                        uses_after_removal.setdefault(sym, []).append(
                            p2.hunk_id)
        for sym, hunk_ids in uses_after_removal.items():
            out.append(Inconsistency(
                kind="removed-definition", symbol=sym,
                hunk_ids=sorted(set(hunk_ids)),
                detail=(f"'{sym}' removed in one hunk but still used in "
                        f"{sorted(set(hunk_ids))}")))

        # 3. conflicting `after` on the same hunk id (two proposals for
        #    the same hunk with different after blocks).
        by_hunk_after: Dict[str, List[str]] = defaultdict(list)
        for p in self.proposals:
            key = p.after.strip()
            if key:
                by_hunk_after[p.hunk_id].append(key)
        for hid, afters in by_hunk_after.items():
            if len(afters) > 1 and len(set(afters)) > 1:
                out.append(Inconsistency(
                    kind="conflicting-after", symbol=hid,
                    hunk_ids=[hid],
                    detail=f"conflicting `after` blocks on hunk {hid}"))

        return out


def reconcile_hunks(proposals: List[HunkProposal]
                    ) -> Tuple[List[HunkProposal], List[Inconsistency]]:
    """tool: reconcile_hunks - detect + reconcile cross-hunk
    inconsistencies.

    For `unpropagated-rename`, the offending hunk's `after` is rewritten
    (old -> new). For `removed-definition`, the removed symbol is
    re-introduced into the dependent hunk's `after` (a `# re-introduce`
    line). For `conflicting-after`, the *longer* (more complete) block is
    kept. Returns (reconciled_proposals, inconsistencies_found).
    """
    checker = CrossHunkConsistency(proposals)
    problems = checker.detect()
    if not problems:
        return proposals, []

    # build the rename map globally
    rename_map: Dict[str, str] = {}
    for p in proposals:
        for old, new in checker._renames(p).items():
            rename_map.setdefault(old, new)

    reconciled: List[HunkProposal] = []
    for p in proposals:
        p = _clone(p)
        # 1. propagate renames
        for old, new in rename_map.items():
            p.after = re.sub(rf"\b{re.escape(old)}\b", new, p.after)
        reconciled.append(p)

    # 2. removed-definition: re-introduce the symbol into dependent hunks
    removed_defs: Set[str] = set()
    for p in proposals:
        removed_defs |= (_identifiers(p.before) - _identifiers(p.after))
    # map hunk -> the dependent hunks that still use a removed def
    dep_by_hunk: Dict[str, Set[str]] = defaultdict(set)
    for p in reconciled:
        for sym in removed_defs:
            if re.search(rf"\b{re.escape(sym)}\b", p.after):
                dep_by_hunk[p.hunk_id].add(sym)
    for hid, syms in dep_by_hunk.items():
        for i, p in enumerate(reconciled):
            if p.hunk_id == hid and syms:
                extra = "".join(f"# re-introduce {s}\n" for s in sorted(syms))
                reconciled[i] = _clone(p)
                reconciled[i].after = extra + p.after
                reconciled[i].rationale = (
                    p.rationale + " [reconciled: re-introduced "
                    + ", ".join(sorted(syms)) + "]")
                break

    # 3. conflicting-after: for the same hunk id with 2+ distinct afters,
    #    keep the longest; drop the duplicates.
    longest_by_hunk: Dict[str, HunkProposal] = {}
    for p in reconciled:
        cur = longest_by_hunk.get(p.hunk_id)
        if cur is None or len(p.after) > len(cur.after):
            longest_by_hunk[p.hunk_id] = p
    final: List[HunkProposal] = []
    seen_hunks: Set[str] = set()
    for p in reconciled:
        if p.hunk_id in seen_hunks:
            continue  # drop the duplicate (a longer one is kept)
        seen_hunks.add(p.hunk_id)
        final.append(longest_by_hunk[p.hunk_id])

    return final, problems


def _clone(p: HunkProposal) -> HunkProposal:
    return HunkProposal(
        file=p.file, hunk_id=p.hunk_id, context=p.context,
        before=p.before, after=p.after, rationale=p.rationale,
        comments=list(p.comments), analyzer=p.analyzer)


def cross_file_summary(proposals: List[HunkProposal]
                       ) -> Dict[str, Any]:
    """tool: cross_file_summary - a per-file digest of the proposals +
    the cross-file symbol dependencies (which files reference symbols
    defined in other files)."""
    by_file: Dict[str, List[str]] = defaultdict(list)
    for p in proposals:
        by_file[p.file].append(p.hunk_id)

    # per-file identifiers (defined = in before, used = in after)
    file_defined: Dict[str, Set[str]] = {}
    file_used: Dict[str, Set[str]] = {}
    for p in proposals:
        file_defined.setdefault(p.file, set())
        file_used.setdefault(p.file, set())
        file_defined[p.file] |= _identifiers(p.before)
        file_used[p.file] |= _identifiers(p.after)

    cross_deps: Dict[str, Dict[str, str]] = {}
    for fname, used in file_used.items():
        for sym in used:
            # find which file defines it (a file != fname that has it in
            # its before)
            owners = [f for f, d in file_defined.items()
                      if f != fname and sym in d]
            if owners:
                cross_deps.setdefault(fname, {})[sym] = owners[0]

    return {
        "n_files": len(by_file),
        "files": {f: {"hunks": hs,
                       "cross_file_symbols": cross_deps.get(f, {})}
                   for f, hs in sorted(by_file.items())},
        "cross_file_symbol_count": sum(
            len(v) for v in cross_deps.values()),
    }
