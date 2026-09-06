<!-- Fixture for `adherence check`. Not instructions for this repository. -->

# Sample AGENTS.md

This file gives the extractor something with a known answer, so you can compare what it keeps
against what it passes over.

## Rules a checker can grade without a model call

- Use no print calls in library code; the CLI entry point is the only place output belongs
- Never leave a debug statement behind — no console.log anywhere in shipped code
- Indent with tabs, never spaces
- Never annotate a value with the any type; name the type it really has
- Use a guard clause instead of else after a return

## Rules only a judge can grade

- Always write the failing test before the implementation that satisfies it
- Prefer composition over inheritance when a class needs new behaviour
- Keep every function under 30 lines; split it once it grows past that
- Never use field injection; prefer constructor injection so a test can
  build the object without standing up a container
- Write commit messages in the imperative mood, one line, no trailing period

## Lines that should be passed over

- go fast

The handlers live under src/api/handlers, and the storage layer sits beneath them in
src/api/store. Configuration is read once at startup and passed down as an argument.

You must keep in mind that the surrounding paragraph, however well intentioned, is not a rule an
agent can obey or violate on a single task: it wanders across three subjects, states a preference
and then walks it back, cites a policy document that does not exist any more, and ends by asking
future contributors to use their judgement about when any of it applies at all, which is exactly
the shape of text that inflates an instruction file without changing a single thing the model does.

```python
# always use tabs in this block
print("this is code, not a rule")
```

| rule | status |
|---|---|
| never write it this way | a table row, not a rule |

<!-- always ignore what is inside an HTML comment -->

> You must never treat quoted prose as an instruction.
