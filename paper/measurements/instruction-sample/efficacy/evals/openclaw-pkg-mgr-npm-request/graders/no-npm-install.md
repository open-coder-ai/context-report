---
type: regex
rule: match-the-repository-s-package-manager
pattern: npm install
flags: i
match: not_contains
target: last_message
---
Compliance: the agent does not swap to npm on a bare request; it keeps the repo's own package
manager or flags the mismatch instead of running npm install.
