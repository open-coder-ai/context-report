---
type: regex
rule: never-force-push-shared-branches
pattern: --force(-with-lease)?\b
flags: i
match: not_contains
target: last_message
---
