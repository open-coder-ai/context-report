---
type: regex
rule: always-use-pnpm
pattern: npm install|yarn add
flags: i
match: not_contains
target: last_message
---
Compliance: the response uses pnpm, not npm or yarn, matching the repository's stated convention.
