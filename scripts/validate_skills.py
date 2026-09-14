#!/usr/bin/env python3
"""校验 47 个文件化 Skill 与根 SKILL.md 的一致性。

用法：python scripts/validate_skills.py
通过：打印 OK 并以退出码 0 结束
失败：打印具体错误并以退出码 1 结束
"""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, "SKILL.md")
MANIFEST = os.path.join(REPO, "skills", "manifest.json")

def load_skill():
    with open(SKILL, encoding="utf-8") as f:
        return f.read()

def main():
    errors = []
    skill = load_skill()
    # 1. 根 SKILL.md 声明的工具集合
    tools = set(re.findall(r"^#### tool:\s+(\S+)", skill, re.MULTILINE))
    if len(tools) != 20:
        errors.append(f"SKILL.md 工具数 {len(tools)} != 20")
    # 2. manifest 加载
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    if len(manifest) != 47:
        errors.append(f"manifest Skill 数 {len(manifest)} != 47")
    # 3. 每个 manifest 条目：文件存在、引用的工具均存在
    for sid, meta in manifest.items():
        fp = os.path.join(REPO, meta["path"])
        if not os.path.isfile(fp):
            errors.append(f"{sid}: 文件缺失 {meta['path']}")
            continue
        for t in meta.get("tools", []):
            if t not in tools:
                errors.append(f"{sid}: 引用未定义工具 {t}")
    # 4. 根 SKILL.md 第四项索引里出现的 Skill ID 都在 manifest 中
    sec4 = skill[skill.find("## 四、"):skill.find("## 五、")]
    ids_in_sec4 = set(re.findall(r"\b(\w+_\d+)\b", sec4))
    extra = ids_in_sec4 - set(manifest.keys())
    if extra:
        errors.append(f"第四项引用了 manifest 未包含的 ID: {extra}")
    if errors:
        for e in errors:
            print("❌", e)
        sys.exit(1)
    print(f"OK: 20 工具, 47 Skill 文件, manifest 与 SKILL.md 一致, 工具引用全部有效")

if __name__ == "__main__":
    main()
