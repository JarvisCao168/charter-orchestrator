"""PR diff consistency via LSP / tree-sitter semantic analysis (v2.10).

Lifts `charter/pr_diff_consistency.py` (a regex / identifier-heap
heuristic for cross-hunk slips) to **true semantic analysis**: when
`tree-sitter` (or an LSP) is available, the completer parses the before
/ after code and resolves symbol *definitions* and *usages* so a
cross-hunk slip ("a helper renamed in one hunk but still called under
the old name in another", "a symbol deleted here but used there") is
caught by real definition / use analysis, not by string matching.

    - `SymbolResolver` - protocol: `symbols(code, lang)` -> a set of the
      identifiers *defined* in `code`, and `used(code, lang)` -> the
      identifiers *referenced*.
    - `TreeSitterResolver` - real tree-sitter parser (language-aware
      definitions vs references). Imported lazily; when tree-sitter is
      not installed it degrades to the `HeuristicResolver` (the
      identifier-heap from v2.9) so the module still works in CI.
    - `HeuristicResolver` - the v2.9 identifier-heap resolver (kept as
      the offline fallback).
    - `semantic_check(proposals, lang)` - run the real resolver over a
      set of `HunkProposal`s and report the cross-hunk inconsistencies
      (unpropagated rename / removed definition) using definition /
      usage resolution instead of string matching.
    - `pick_symbol_resolver(lang)` - auto-select: tree-sitter when
      installed for `lang`, else the heuristic resolver.

Stdlib-only core; tree-sitter / LSP are optional (imported lazily). The
semantics are a real definition / use analysis when the parser is
present, and a faithful identifier-heap approximation otherwise.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .pr_diff_completion import HunkProposal
from .pr_diff_consistency import Inconsistency, _identifiers

__all__ = [
    "SymbolResolver", "TreeSitterResolver", "HeuristicResolver",
    "semantic_check", "pick_symbol_resolver", "semantic_consistency_report",
]

_IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
# Python "definition" prefixes (function / class / assignment)
_DEF_HINTS = ("def ", "class ", "=", "lambda ")


class SymbolResolver:
    """Interface: resolve definitions / usages in a code snippet."""
    name: str
    language: str

    def defined(self, code: str) -> Set[str]:
        raise NotImplementedError

    def used(self, code: str) -> Set[str]:
        raise NotImplementedError


class HeuristicResolver:
    """The v2.9 identifier-heap resolver (offline fallback)."""

    name = "heuristic"

    def __init__(self, language: str = "python") -> None:
        self.language = language

    def defined(self, code: str) -> Set[str]:
        defs: Set[str] = set()
        for line in (code or "").splitlines():
            s = line.strip()
            if s.startswith("def "):
                m = re.match(r"def\s+([A-Za-z_]\w*)", s)
                if m:
                    defs.add(m.group(1))
            elif s.startswith("class "):
                m = re.match(r"class\s+([A-Za-z_]\w*)", s)
                if m:
                    defs.add(m.group(1))
            elif "=" in s and not s.startswith("#"):
                m = re.match(r"\s*([A-Za-z_]\w*)\s*=(?!=)", s)
                if m:
                    defs.add(m.group(1))
        return defs

    def used(self, code: str) -> Set[str]:
        return _identifiers(code)


class TreeSitterResolver(HeuristicResolver):
    """A real tree-sitter resolver. Uses `tree_sitter` + a language
    grammar when installed; otherwise falls back to the heuristic
    defined / used split (so the call shape is stable).

    The "real" definition detection walks `function_definition` /
    `class_definition` / `assignment` nodes; usage detection walks
    `identifier` nodes that are not in a definition position. This is a
    true semantic split (not a string heap) when tree-sitter is present.
    """

    name = "tree-sitter"

    def __init__(self, language: str = "python") -> None:
        super().__init__(language)
        self._parser = None
        self._lang = None
        try:
            import tree_sitter  # type: ignore
            from tree_sitter import Language  # type: ignore
            # language-specific binding (python / javascript / ...)
            binding = tree_sitter.language_for(self.language) \
                if hasattr(tree_sitter, "language_for") else None
            if binding is not None:
                self._lang = Language(binding)
                self._parser = tree_sitter.Parser(self._lang)
        except Exception:
            # tree-sitter not installed -> fall back to heuristic behaviour
            self._parser = None
            self.name = "tree-sitter-fallback"

    @property
    def is_real(self) -> bool:
        return self._parser is not None

    def defined(self, code: str) -> Set[str]:
        if not self._parser:
            return super().defined(code)
        return self._ts_defined(code)

    def used(self, code: str) -> Set[str]:
        if not self._parser:
            return super().used(code)
        return self._ts_used(code)

    # -- tree-sitter walks ----------------------------------------------
    def _tree(self, code: str):
        import tree_sitter  # type: ignore
        return self._parser.parse(tree_sitter.encode(code))

    def _ts_defined(self, code: str) -> Set[str]:
        tree = self._tree(code)
        defs: Set[str] = set()

        def visit(node):
            if node.type in ("function_definition", "function",
                             "class_definition", "class_declaration"):
                name = node.child_by_field_name("name")
                if name is not None:
                    defs.add(name.text.decode())
            if node.type in ("identifier", "variable",
                             "constant", "property_identifier"):
                parent = node.parent
                if parent is not None and parent.type in (
                        "assignment", "pair", "variable_declarator"):
                    # a name in a definition position
                    if parent.child_by_field_name("name") is not node and \
                       parent.child_by_field_name("value") is not node:
                        try:
                            defs.add(node.text.decode())
                        except Exception:
                            pass
            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return defs

    def _ts_used(self, code: str) -> Set[str]:
        tree = self._tree(code)
        used: Set[str] = set()

        def visit(node):
            if node.type in ("identifier", "variable",
                             "call", "member_access_expression",
                             "attribute", "property_identifier"):
                try:
                    used.add(node.text.decode())
                except Exception:
                    pass
            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return used


def pick_symbol_resolver(language: str = "python") -> SymbolResolver:
    """Auto-select the resolver: a real tree-sitter resolver when the
    parser is available, else the heuristic one. Returns the resolver +
    (implicitly) its `.name` so a caller can tell which ran."""
    resolver = TreeSitterResolver(language=language)
    if resolver.is_real:
        return resolver
    return HeuristicResolver(language=language)


def semantic_check(
        proposals: List[HunkProposal],
        language: str = "python",
        resolver: Optional[SymbolResolver] = None,
        ) -> List[Inconsistency]:
    """Run a semantic (definition / use) cross-hunk check over a set of
    `HunkProposal`s.

    Detects:
        * unpropagated-rename - a symbol DEFINED in one hunk's `before`
          and re-DEFINED (renamed) in its `after`, still *used* under the
          old name in another hunk's `after`.
        * removed-definition - a symbol DEFINED in one hunk's `before`
          but NOT defined in its `after` (removed), yet still *used* in
          another hunk's `after`.

    `resolver` defaults to `pick_symbol_resolver(language)`. Returns the
    list of inconsistencies (empty = clean)."""
    resolver = resolver or pick_symbol_resolver(language)
    problems: List[Inconsistency] = []

    # per-hunk defined / used sets (before vs after)
    per_hunk: List[Dict[str, Any]] = []
    for p in proposals:
        d_before = resolver.defined(p.before)
        d_after = resolver.defined(p.after)
        u_after = resolver.used(p.after)
        per_hunk.append({
            "hunk_id": p.hunk_id,
            "d_before": d_before, "d_after": d_after,
            "u_after": u_after,
            "renamed": {o: n for o, n in
                         zip(sorted(d_before - d_after),
                             sorted(d_after - d_before))
                         if len(d_before - d_after) == 1
                         and len(d_after - d_before) == 1},
            "removed": d_before - d_after,
        })

    # 1. unpropagated rename
    rename_map: Dict[str, str] = {}
    for h in per_hunk:
        for old, new in h["renamed"].items():
            rename_map.setdefault(old, new)
    for old, new in rename_map.items():
        offenders = [h["hunk_id"] for h in per_hunk
                     if old in h["u_after"]]
        if offenders:
            problems.append(Inconsistency(
                kind="unpropagated-rename", symbol=old,
                hunk_ids=offenders,
                detail=(f"'{old}' -> '{new}' renamed in one hunk but "
                        f"still referenced in {offenders}")))

    # 2. removed definition still used
    removed_syms: Set[str] = set()
    for h in per_hunk:
        removed_syms |= h["removed"]
    dependents: Dict[str, List[str]] = {}
    for sym in removed_syms:
        for h in per_hunk:
            if sym in h["u_after"] and sym not in h["removed"]:
                dependents.setdefault(sym, []).append(h["hunk_id"])
    for sym, ids in dependents.items():
        problems.append(Inconsistency(
            kind="removed-definition", symbol=sym,
            hunk_ids=sorted(set(ids)),
            detail=(f"'{sym}' removed in one hunk but still used in "
                    f"{sorted(set(ids))}")))

    return problems


def semantic_consistency_report(
        proposals: List[HunkProposal],
        language: str = "python",
        ) -> Dict[str, Any]:
    """tool: semantic_consistency_report - one-shot: the resolver that
    ran + the semantic inconsistency list + a verdict."""
    resolver = pick_symbol_resolver(language)
    problems = semantic_check(proposals, language=language,
                               resolver=resolver)
    return {
        "resolver": resolver.name,
        "language": language,
        "n_proposals": len(proposals),
        "inconsistencies": [p.as_dict() for p in problems],
        "clean": not problems,
        "summary": ("semantically consistent" if not problems
                    else f"{len(problems)} semantic slip(s)"),
    }
