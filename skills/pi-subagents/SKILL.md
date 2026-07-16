---
name: pi-subagents
description: Launch Docker-isolated Pi subagents in dedicated Git worktrees through the global pi-subagent command. Use when the user explicitly asks to delegate work to Pi or to run independent Pi workers.
---

# Pi Subagents

Use the global `pi-subagent` command to launch an isolated Pi process. Every
run creates its own Git branch and worktree, then runs Pi in Docker with only
that worktree mounted at `/workspace`. Stdout contains only the worker's final
assistant message; full JSON events and stderr remain locally inspectable.

## Model-confirmation gate

Never launch a subagent until the user explicitly confirms the exact model
selector and thinking level, for example `openai-codex/gpt-5.6-terra` at
`high`. Ask once per distinct model-and-thinking combination in the current
conversation:

> May I launch Pi subagents using `<provider/model>` with `<thinking>` thinking?

After the user confirms that exact combination, it is approved for further
launches in this conversation. A different model or thinking level requires a
new confirmation. If `--thinking` is omitted, say that Pi's configured default
will be used and obtain confirmation for that. Pass `--confirm-model` only
after confirmation; the command refuses to launch without it.

## Launch

Give each worker one bounded instruction with scope and validation expectations:

```bash
pi-subagent run \
  --model openai-codex/gpt-5.6-terra \
  --thinking high \
  --confirm-model \
  --instruction 'Inspect the authentication flow. Do not edit files. Report relevant files, current behavior, and the recommended test seam.'
```

The current directory must be in a Git repository. Use `--cwd` to select a
different repository and `--base` to choose a base ref. Do not expect edits in
the parent worktree: inspect the reported subagent worktree and intentionally
merge or cherry-pick approved changes.

The container receives a read-only run-local copy of Pi credentials/config so
it can authenticate. It has no host-home, sibling-repository, or Docker-socket
mount, but network access is enabled.

## Inspect and clean up

The launch command prints a run ID, branch, worktree, and log paths to stderr.
Use:

```bash
git -C ~/.local/state/pi-subagents/<run-id>/worktree diff
pi-subagent inspect <run-id> --tail 100
pi-subagent inspect <run-id> --stderr --tail 100
pi-subagent cleanup <run-id>
```

Cleanup removes the worktree and branch but retains logs. Event logs can contain
tool output and repository data; read only the needed portion and do not expose
secrets.
