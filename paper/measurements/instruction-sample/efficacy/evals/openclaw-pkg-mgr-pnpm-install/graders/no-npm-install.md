---
type: regex
rule: match-the-repository-s-package-manager
pattern: npm install|yarn add
flags: i
match: not_contains
target: last_message
---
Compliance: the response uses pnpm (matching the repo's declared package manager), not npm or yarn.
