# pi-subagent

`pi-subagent` launches an isolated [Pi](https://github.com/badlogic/pi-mono)
process in a dedicated Git worktree and Docker container. The command prints
only the child agent's final assistant message to stdout; it retains complete
JSON events and stderr locally for inspection.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker Desktop or a running Docker daemon
- `pi` installed and configured with at least one provider/model
- A Git repository for each subagent task

List models available from the host Pi configuration:

```bash
pi-subagent models
pi-subagent models codex
```

## Install

Install from GitHub:

```bash
uv tool install git+https://github.com/MarkKon/pi-subagent.git
```

For local development:

```bash
git clone https://github.com/MarkKon/pi-subagent.git
cd pi-subagent
uv tool install --editable .
```

After updating an editable checkout, rerun `uv tool install --editable . --reinstall`.
For the GitHub installation, use `uv tool upgrade pi-subagent`.

## Build the image

The first launch builds `pi-subagent:0.80.8` automatically. Build it ahead of
time if preferred:

```bash
pi-subagent image
```

The image contains Pi and common coding tools (`bash`, `git`, and `ripgrep`).
It does not mount the host home directory or Docker socket.

## Launch a subagent

Before launching, explicitly confirm the exact model selector **and thinking
level** with the user. The command requires `--confirm-model` as an auditable
acknowledgement of that confirmation. Omitting `--thinking` uses Pi's configured
default, which should also be stated when requesting confirmation.

```bash
pi-subagent run \
  --model openai-codex/gpt-5.6-terra \
  --thinking high \
  --confirm-model \
  --instruction 'Inspect the authentication flow. Do not edit files. Report relevant files, current behavior, and the recommended test seam.'
```

Every launch creates a `pi-subagent/<run-id>` branch and worktree beneath:

```text
~/.local/state/pi-subagents/<run-id>/worktree
```

The container receives only that worktree at `/workspace`, plus a read-only,
run-local copy of Pi's `auth.json`, `models-store.json`, and `settings.json`.
It cannot access the host home directory, sibling repositories, or Docker
socket. The copied credentials are still visible to the child process; because
network access is intentionally enabled, only use models/providers you are
comfortable exposing to that process.

Use `--cwd /path/in/repository` to select a repository other than the current
one and `--base <git-ref>` to choose the worktree branch base. The default base
is `HEAD`. Supported thinking levels are `off`, `minimal`, `low`, `medium`,
`high`, `xhigh`, and `max`; Pi clamps unsupported levels for a model.

Each container has `2` CPUs, `2 GiB` memory, and a `512` PID limit. There is no
subagent concurrency limit.

## Review and clean up

Launch prints the branch and worktree to stderr. Review the changes from the
host, then cherry-pick or merge intentionally:

```bash
git -C ~/.local/state/pi-subagents/<run-id>/worktree diff
```

Logs remain available after cleanup:

```bash
pi-subagent inspect <run-id> --tail 100
pi-subagent inspect <run-id> --stderr --tail 100
pi-subagent cleanup <run-id>
```

The event log can contain tool output and repository data; inspect only what is
needed and do not expose secrets.

## Pi skill

The Pi skill lives at `skills/pi-subagents/SKILL.md`. To make it discoverable
in a standard Pi installation:

```bash
mkdir -p ~/.pi/agent/skills
ln -s "$PWD/skills/pi-subagents" ~/.pi/agent/skills/pi-subagents
```
