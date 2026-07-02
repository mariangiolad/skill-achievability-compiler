# Real-skill scan report

`skillc 0.3.0` run over the public skills corpus ([anthropics/skills](https://github.com/anthropics/skills)): 32 `SKILL.md` files, checked under each capability profile.  Regenerate with `python3 scripts/make_report.py <dir>`.

A verdict is always *relative to a capability context*: `IMPOSSIBLE [MISSING_CAPABILITY]` means the skill's instructions invoke a tool that this runtime does not grant -- the skill cannot be carried out as written there.  It is not a defect of the skill.

| skill | claude-ai | claude-code |
|---|---|---|
| `examples/algorithmic-art` | ACHIEVABLE | ACHIEVABLE |
| `examples/benepass-reimbursement` | ACHIEVABLE | IMPOSSIBLE (`read_page`, `upload_file`) |
| `examples/brand-guidelines` | ACHIEVABLE | ACHIEVABLE |
| `examples/call-to-book` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/cancel-unsubscribe` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/canvas-design` | ACHIEVABLE | ACHIEVABLE |
| `examples/doc-coauthoring` | ACHIEVABLE | IMPOSSIBLE (`create_file`, `str_replace`) |
| `examples/event-planning` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/file-expenses` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/file-form` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/financial-calculator` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/grocery-shopping` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/hire-help` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/internal-comms` | ACHIEVABLE | ACHIEVABLE |
| `examples/learn` | ACHIEVABLE | IMPOSSIBLE (`read_me`, `show_widget`) |
| `examples/mcp-builder` | ACHIEVABLE | ACHIEVABLE |
| `examples/meal-delivery` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/prescription-refill` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/return-refund` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/setup-writing-style` | ACHIEVABLE | IMPOSSIBLE (`search_mcp_registry`) |
| `examples/skill-creator` | ACHIEVABLE | ACHIEVABLE |
| `examples/slack-gif-creator` | ACHIEVABLE | ACHIEVABLE |
| `examples/theme-factory` | ACHIEVABLE | ACHIEVABLE |
| `examples/web-artifacts-builder` | ACHIEVABLE | ACHIEVABLE |
| `public/docx` | ACHIEVABLE | ACHIEVABLE |
| `public/file-reading` | ACHIEVABLE | ACHIEVABLE |
| `public/frontend-design` | ACHIEVABLE | ACHIEVABLE |
| `public/pdf` | ACHIEVABLE | ACHIEVABLE |
| `public/pdf-reading` | ACHIEVABLE | ACHIEVABLE |
| `public/pptx` | ACHIEVABLE | ACHIEVABLE |
| `public/product-self-knowledge` | ACHIEVABLE | ACHIEVABLE |
| `public/xlsx` | ACHIEVABLE | ACHIEVABLE |

**Totals:** 32/32 achievable under `claude-ai`, 17/32 achievable under `claude-code`
