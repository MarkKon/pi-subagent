# pi-subagent

A `uv`-installed command for launching an isolated `pi` process with an explicit model selector. It returns only the final assistant message while retaining the complete JSON event log locally.

## Install

```bash
uv tool install --editable .
```

## Use

Confirm the exact model with the user before launching, then:

```bash
pi-subagent run \
  --model openai-codex/gpt-5.6-terra \
  --confirm-model \
  --instruction 'Inspect the authentication flow. Do not edit files.'
```

Inspect retained output:

```bash
pi-subagent inspect <run-id> --tail 100
pi-subagent inspect <run-id> --stderr --tail 100
```
