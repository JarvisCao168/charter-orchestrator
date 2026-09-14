# Charter SOP Template Marketplace / SOP 行业模板市场

Drop a `.json` here to ship an industry SOP template. `charter.templates.load_template(name)`
discovers it automatically. Each file:

```json
{
  "name": "my-industry",
  "label": "My Industry",
  "stage_gates": { "stage_6": ["...checks..."] },
  "tdd_enforcement": "strict",
  "token_budget": 80000,
  "guardrail_extra_patterns": ["(?i)some_pattern"],
  "audit_required_stages": ["stage_5", "stage_8"]
}
```

Builtin: `finance.json` (SOC2-aligned, strict), `healthcare.json` (HIPAA, PHI-aware),
`e-commerce.json` (high-throughput, soft), `research.json` (reproducible, off).

> 把行业 SOP 模板放到这个目录即可被 `list_templates()` 发现。内置：金融 / 医疗 / 电商 / 研究。
