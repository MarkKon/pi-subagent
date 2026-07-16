# pi-subagent

`pi-subagent` launches an isolated [Pi](https://github.com/badlogic/pi-mono)
process with an explicit model selector. It prints only the child agent's final
assistant message to stdout and retains the complete JSON event stream locally
for inspection.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- `pi` installed and configured with at least one provider/model

List models available on the current host:

```bash
pi-subagent models
pi-subagent models codex
```

## Install

Install the published GitHub repository as a uv tool:

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

## Launch a subagent

Before launching, explicitly confirm the exact model selector with the user.
The command requires `--confirm-model` as an auditable acknowledgement of that
confirmation.

```bash
pi-subagent run \
  --model openai-codex/gpt-5.6-terra \
  --confirm-model \
  --instruction 'Inspect the authentication flow. Do not edit files. Report relevant files, current behavior, and the recommended test seam.'
```

Use `--cwd /path/to/worktree` to choose the child process's working directory.
Avoid parallel implementation workers in the same directory.

## Inspect a run

Each run prints its ID and retained log paths to stderr. The logs are private
files under `~/.local/state/pi-subagents/<run-id>/`:

```bash
pi-subagent inspect <run-id> --tail 100
pi-subagent inspect <run-id> --stderr --tail 100
```

The JSON event log can contain tool output and repository data; inspect only
what is needed and do not expose secrets.

## Pi skill

The Pi skill lives at `skills/pi-subagents/SKILL.md`. To make it discoverable
in a standard Pi installation:

```bash
mkdir -p ~/.pi/agent/skills
ln -s "$PWD/skills/pi-subagents" ~/.pi/agent/skills/pi-subagents
```
