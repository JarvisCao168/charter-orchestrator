# 贡献指南

## 提交规范
遵循 [Conventional Commits](https://www.conventionalcommits.org/)。

## 新增 Skill
1. Fork 并创建分支 `skill/<your-skill-name>`
2. 在 `skills/<category>/<skill_id>/` 新建目录，写入含 frontmatter 的 `SKILL.md`
3. 同步更新 `skills/manifest.json` 与根 `SKILL.md` 第四项索引
4. 运行 `python scripts/validate_skills.py` 确保通过
5. 提交 PR，标题：`feat(skill): 新增 XxxSkill - 一句话描述`

## 校验
任何 Skill/工具/规则变更必须先跑：
```
python scripts/validate_skills.py
```
