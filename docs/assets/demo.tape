Output docs/assets/demo.gif
Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 640
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 24

Hide
Type `export HOME=$(mktemp -d) && cd $(mktemp -d) && mkdir -p my-plugin/hooks`
Enter
Type `cat > my-plugin/hooks/guard.py <<'PY'`
Enter
Type `#!/usr/bin/env python3`
Enter
Type `import json, sys`
Enter
Type `event = json.load(sys.stdin)`
Enter
Type `command = event.get("tool_input", {}).get("command", "")`
Enter
Type `if "destructive-pattern" in command:`
Enter
Type `    print(json.dumps({"decision": "deny", "reason": "blocked destructive command"}))`
Enter
Type `sys.exit(0)`
Enter
Type `PY`
Enter
Type `cat > my-plugin/hooks/hooks.json <<'JSON'`
Enter
Type `{`
Enter
Type `  "hooks": {`
Enter
Type `    "PreToolUse": [`
Enter
Type `      {"hooks": [{"command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"]}]}`
Enter
Type `    ]`
Enter
Type `  }`
Enter
Type `}`
Enter
Type `JSON`
Enter
Type `clear`
Enter
Show

# The subject: my-plugin, a two-file Claude Code plugin bundle (my-plugin/hooks/{guard.py,
# hooks.json}) declaring one PreToolUse hook that denies a command containing "destructive-pattern"
# -- the same commands as the README's own quickstart block.
Type `context-report produce --subject ./my-plugin --kind plugin --target claude_code --n 20 --out report.json`
Enter
Sleep 4s

Type `context-report verify report.json --subject ./my-plugin`
Enter
Sleep 4s
