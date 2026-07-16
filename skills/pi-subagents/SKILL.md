---
name: pi-subagents
description: Launch isolated Pi subagents through the global pi-subagent command, selecting a provider/model and instruction. Use when the user explicitly asks to delegate work to Pi or to run independent Pi workers.
---

# Pi Subagents

Use the global `pi-subagent` command to launch an isolated Pi process. It
returns only the worker's final assistant message on stdout and stores the full
JSON event stream locally for later inspection.

## Model-confirmation gate

Never launch a subagent until the user explicitly confirms the exact model
selector, for example `openai-codex/gpt-5.6-terra`. Ask once per distinct model
in the current conversation:

> May I launch Pi subagents using `<provider/model>`?

After the user confirms that exact model, it is approved for further launches
in this conversation. A different model requires a new confirmation. Pass
`--confirm-model` only after that confirmation; the command refuses to launch
without it.

## Launch

Give each worker one bounded instruction with scope and validation expectations:

```bash
pi-subagent run \
  --model openai-codex/gpt-5.6-terra \
  --confirm-model \
  --instruction 'Inspect the authentication flow. Do not edit files. Report relevant files, current behavior, and the recommended test seam.'
```

Use `--cwd /path/to/worktree` when the worker must operate in another
worktree. Do not run parallel implementation workers in the same directory.
The parent agent is still responsible for inspecting diffs and verifying
claimed checks.

## Inspect a run

The launch command prints a run ID and log paths to stderr. To inspect retained
output, use:

```bash
pi-subagent inspect <run-id> --tail 100
pi-subagent inspect <run-id> --stderr --tail 100
```

The event log can contain tool output and repository data. Read only the
needed portion and do not expose secrets.
