---
name: retry-research
description: Search in a retry loop until a result is found, then deliver a researched answer. Demonstrates the tail-recursive fragment (rec/continue).
---

# Retry research

Search repeatedly until something is found, then deliver the answer.

```skillc-pack
{
  "name": "retry-research",
  "roles": ["worker"],
  "capabilities": {
    "search": {"owner": "worker", "add": ["found"]},
    "deliver": {"owner": "worker", "pre": "found", "add": ["answered"]}
  },
  "protocol": [
    {"rec": {"name": "X", "body": [
      {"act": {"cap": "search", "by": "worker"}},
      {"choice": {"by": "worker", "branches": {
        "retry": [{"continue": "X"}],
        "found": []
      }}}
    ]}},
    {"act": {"cap": "deliver", "by": "worker"}}
  ],
  "goal": "answered"
}
```
