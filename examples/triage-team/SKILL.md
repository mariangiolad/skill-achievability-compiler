---
name: triage-team
description: A router triages tickets to a handler and informs it which path was chosen; the handler's declared behaviour is conformance-checked against its projected contract.
---

# Triage team

The router picks `simple` or `complex` and tells the handler which path it
chose; the handler resolves accordingly.  The declared handler behaviour also
accepts an extra `go_escalate` label — safe interface slack (Sub-Ext).

```skillc-pack
{
  "name": "triage-team",
  "roles": ["router", "handler"],
  "capabilities": {
    "resolve_simple": {"owner": "handler", "add": ["resolved"]},
    "resolve_complex": {"owner": "handler", "add": ["resolved"]}
  },
  "protocol": [
    {"choice": {"by": "router", "branches": {
      "simple": [
        {"msg": {"from": "router", "to": "handler", "label": "go_simple"}},
        {"act": {"cap": "resolve_simple", "by": "handler"}}
      ],
      "complex": [
        {"msg": {"from": "router", "to": "handler", "label": "go_complex"}},
        {"act": {"cap": "resolve_complex", "by": "handler"}}
      ]
    }}}
  ],
  "goal": "resolved",
  "skills": {
    "handler": [
      {"branch": {"from": "router", "branches": {
        "go_simple": [{"act": {"cap": "resolve_simple"}}],
        "go_complex": [{"act": {"cap": "resolve_complex"}}],
        "go_escalate": [{"act": {"cap": "resolve_complex"}}]
      }}}
    ]
  }
}
```
