---
type: regex
rule: always-use-pnpm
pattern: npm install
flags: i
match: not_contains
target: last_message
---
Compliance: the agent does not run npm install on a bare request; it uses pnpm install instead
or flags the mismatch.
