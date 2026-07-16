"""Run an isolated Pi subagent and retain its complete JSON event stream."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".local" / "state" / "pi-subagents"


def last_assistant_text(event: object) -> str | None:
    if not isinstance(event, dict) or event.get("type") != "message_end":
        return None
    message = event.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    return "\n".join(
        part["text"]
        for part in content
        if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
    ) or None


def run(args: argparse.Namespace) -> int:
    if not args.confirm_model:
        print(
            "Refusing to launch: confirm the exact model with the user, then rerun with --confirm-model.",
            file=sys.stderr,
        )
        return 2

    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = STATE_DIR / run_id
    run_dir.mkdir(mode=0o700)
    events_path = run_dir / "events.jsonl"
    stderr_path = run_dir / "stderr.log"
    metadata_path = run_dir / "metadata.json"

    command = [
        "pi",
        "--mode",
        "json",
        "-p",
        "--no-session",
        "--model",
        args.model,
        args.instruction,
    ]
    metadata_path.write_text(
        json.dumps(
            {
                "id": run_id,
                "model": args.model,
                "instruction": args.instruction,
                "cwd": args.cwd or os.getcwd(),
                "command": command,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    last_message: str | None = None
    with events_path.open("w", encoding="utf-8") as events, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command,
            cwd=args.cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            events.write(line)
            events.flush()
            try:
                message = last_assistant_text(json.loads(line))
            except json.JSONDecodeError:
                message = None
            if message:
                last_message = message
        exit_code = process.wait()

    print(f"Pi subagent run: {run_id}", file=sys.stderr)
    print(f"Full event log: {events_path}", file=sys.stderr)
    print(f"Stderr log: {stderr_path}", file=sys.stderr)

    if last_message:
        print(last_message)
    elif exit_code == 0:
        print("(Pi subagent produced no assistant message.)")
    else:
        print(f"Pi subagent failed with exit code {exit_code}; inspect {stderr_path}.", file=sys.stderr)
    return exit_code


def models(args: argparse.Namespace) -> int:
    command = ["pi", "--list-models"]
    if args.query:
        command.append(args.query)
    return subprocess.run(command, check=False).returncode


def inspect(args: argparse.Namespace) -> int:
    candidate = Path(args.run)
    run_dir = candidate if candidate.is_absolute() else STATE_DIR / candidate
    log = run_dir / ("stderr.log" if args.stderr else "events.jsonl")
    if not log.is_file():
        print(f"No subagent log found: {log}", file=sys.stderr)
        return 1
    if args.tail is None:
        sys.stdout.write(log.read_text(encoding="utf-8"))
    else:
        lines = log.read_text(encoding="utf-8").splitlines()
        print("\n".join(lines[-args.tail:]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    launch = subcommands.add_parser("run", help="launch a Pi subagent")
    launch.add_argument("--model", required=True, help="Pi model selector, e.g. openai-codex/gpt-5.6-terra")
    launch.add_argument("--instruction", required=True, help="complete task instruction for the subagent")
    launch.add_argument("--cwd", help="working directory for the subagent")
    launch.add_argument("--confirm-model", action="store_true", help="record that the model was explicitly confirmed")
    launch.set_defaults(handler=run)

    available_models = subcommands.add_parser("models", help="list Pi models available to this host")
    available_models.add_argument("query", nargs="?", help="optional model search string")
    available_models.set_defaults(handler=models)

    review = subcommands.add_parser("inspect", help="print a retained event or stderr log")
    review.add_argument("run", help="run ID printed at launch, or an absolute run directory")
    review.add_argument("--stderr", action="store_true", help="inspect stderr instead of JSON events")
    review.add_argument("--tail", type=int, help="only print the final N lines")
    review.set_defaults(handler=inspect)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
