#!/usr/bin/env python3
"""Validate the 47 file-based Skills, the manifest structure, and the executable core.

Usage: python scripts/validate_skills.py
Exit 0 = all green, exit 1 = failures listed.
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "SKILL.md")
MANIFEST = os.path.join(REPO, "skills", "manifest.json")

def main():
    errors = []
    with open(SKILL, encoding="utf-8") as f:
        skill = f.read()
    # 1. Tools declared in SKILL.md
    tools = set(re.findall(r"^#### tool:\s+(\S+)", skill, re.MULTILINE))
    if len(tools) != 20:
        errors.append(f"SKILL.md tool count {len(tools)} != 20")
    # 2. Manifest (new nested structure)
    with open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)
    skills = m.get("skills", {})
    if len(skills) != 47:
        errors.append(f"manifest skills {len(skills)} != 47")
    if "tools" not in m or set(m["tools"]) != tools:
        errors.append("manifest tools block not in sync with SKILL.md")
    # 3. Each skill: file exists, referenced tools valid
    for sid, meta in skills.items():
        fp = os.path.join(REPO, meta["path"])
        if not os.path.isfile(fp):
            errors.append(f"{sid}: missing file {meta['path']}")
            continue
        for t in meta.get("tools", []):
            if t not in tools:
                errors.append(f"{sid}: references undefined tool {t}")
    # 4. Skill IDs in SKILL.md section four all present in manifest
    sec4 = skill[skill.find("## 四、"):skill.find("## 五、")]
    ids_in_sec4 = set(re.findall(r"\b(\w+_\d+)\b", sec4))
    extra = ids_in_sec4 - set(skills.keys())
    if extra:
        errors.append(f"section four references IDs missing from manifest: {extra}")
    # 5. Executable core present
    core = os.path.join(REPO, "charter", "core.py")
    if not os.path.isfile(core):
        errors.append("missing executable core: charter/core.py")
    if errors:
        for e in errors:
            print("FAIL", e)
        sys.exit(1)
    print(f"OK: 20 tools, 47 skill files, manifest structure valid, executable core present")

if __name__ == "__main__":
    main()
