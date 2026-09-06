"""Per-subject rule-extraction stats for the instruction-sample: rules, skips, and why.

Reads each subject's injected text file(s) with `context_report.efficacy.rules.extract_all`
and writes `extract_stats.json` alongside this script: one entry per subject with rules
extracted, lines skipped by reason, and the extracted rule ids, in source order.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from context_report.efficacy.rules import extract_all
from context_report.produce.cost import injected_text_paths

HERE = Path(__file__).parent

# (subject id, subject path, kind) — the same seven subjects produced under this directory.
SUBJECTS = [
    ("openclaw-agents-md", "openclaw/AGENTS.md", "instruction-file"),
    ("openclaw-github-skill", "openclaw/skills/github", "skill"),
    (
        "openclaw-inventory-agent-subagent",
        "openclaw/.agents/skills/technical-documentation/agents/inventory-agent.md",
        "subagent",
    ),
    ("karpathy-read-arxiv-paper-skill", "nanochat/.claude/skills/read-arxiv-paper", "skill"),
    ("n8n-agents-md", "n8n/AGENTS.md", "instruction-file"),
    ("bun-claude-md", "bun/CLAUDE.md", "instruction-file"),
    ("transformers-agents-md", "transformers/.ai/AGENTS.md", "instruction-file"),
]

USAGE = (
    "usage: extract_stats.py CLONES_ROOT  (a directory holding openclaw/, nanochat/, n8n/, "
    "bun/, transformers/ at the commits in inventory.json)"
)


def main() -> None:
    if len(sys.argv) != 2:  # noqa: PLR2004 -- one positional argument
        raise SystemExit(USAGE)
    root = Path(sys.argv[1])
    out = {}
    for subject_id, rel_path, kind in SUBJECTS:
        path = root / rel_path
        extraction = extract_all(injected_text_paths(path, kind))
        out[subject_id] = {
            "path": rel_path,
            "kind": kind,
            "rules_extracted": len(extraction.rules),
            "skipped": extraction.skipped,
            "rule_ids": [r.id for r in extraction.rules],
        }
    (HERE / "extract_stats.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))  # noqa: T201 -- a script's output


if __name__ == "__main__":
    main()
