---
name: embedded-pack
description: A skill whose author embedded a precise achievability pack. The pack encodes a budget refinement the prose only hints at.
---

# Book travel under budget

Search for flights and book only if the fare is under 500.

```skillc-pack
{
  "name": "embedded-pack",
  "roles": ["agent"],
  "capabilities": {
    "search": {"owner": "agent", "add": ["searched"]},
    "book_cheap": {"owner": "agent", "pre": "searched", "add": ["booked"],
                    "nondet": {"price": {"cmp": ["price", "<", 500]}}}
  },
  "protocol": [
    {"act": {"cap": "search", "by": "agent"}},
    {"act": {"cap": "book_cheap", "by": "agent"}}
  ],
  "goal": {"and": ["booked", {"cmp": ["price", "<", 500]}]}
}
```
