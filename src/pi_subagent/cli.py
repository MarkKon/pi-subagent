"""Launch Pi subagents in Docker-isolated Git worktrees."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".local" / "state" / "pi-subagents"
DEFAULT_IMAGE = "pi-subagent:0.80.8"

DOCKERFILE = """\
FROM node:24-bookworm-slim
RUN apt-get update \\
 && apt-get install -y --no-install-recommends bash ca-certificates git ripgrep \\
 && rm -rf /var/lib/apt/lists/*
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.80.8
WORKDIR /workspace
ENTRYPOINT ["pi"]
"""


def run_command(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


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


def create_run_dir() -> tuple[str, Path]:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = STATE_DIR / run_id
    run_dir.mkdir(mode=0o700)
    return run_id, run_dir


def copy_pi_agent_config(destination: Path) -> None:
    """Copy only Pi's provider/settings files, never the host session history."""
    source = Path.home() / ".pi" / "agent"
    destination.mkdir(mode=0o700, parents=True)
    for filename in ("auth.json", "models-store.json", "settings.json"):
        candidate = source / filename
        if candidate.is_file():
            shutil.copy2(candidate, destination / filename)
    if not (destination / "auth.json").is_file():
        raise RuntimeError(f"Pi credentials not found at {source / 'auth.json'}.")
    os.chmod(destination, 0o700)
    for file in destination.iterdir():
        os.chmod(file, 0o600)


def ensure_image(image: str) -> None:
    try:
        present = subprocess.run(
            ["docker", "image", "inspect", image], check=False, capture_output=True, text=True
        ).returncode == 0
    except FileNotFoundError as error:
        raise RuntimeError("Docker CLI is not installed or is not on PATH.") from error
    if present:
        return

    print(f"Building Docker image {image}...", file=sys.stderr)
    completed = subprocess.run(
        ["docker", "build", "--tag", image, "-"],
        input=DOCKERFILE,
        text=True,
        stdout=sys.stderr,
        stderr=sys.stderr,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Could not build Docker image {image}.")


def create_worktree(repository: Path, run_dir: Path, run_id: str, base: str) -> tuple[str, Path]:
    root = Path(run_command(["git", "-C", str(repository), "rev-parse", "--show-toplevel"])).resolve()
    worktree = run_dir / "worktree"
    branch = f"pi-subagent/{run_id}"
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "--quiet", "-b", branch, str(worktree), base],
        check=True,
    )
    return branch, worktree


def write_metadata(run_dir: Path, metadata: dict[str, object]) -> None:
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    if not args.confirm_model:
        print(
            "Refusing to launch: confirm the exact model and thinking level with the user, then rerun with --confirm-model.",
            file=sys.stderr,
        )
        return 2

    try:
        ensure_image(args.image)
        run_id, run_dir = create_run_dir()
        repository = Path(args.cwd or os.getcwd()).resolve()
        branch, worktree = create_worktree(repository, run_dir, run_id, args.base)
        pi_agent_dir = run_dir / "pi-agent"
        copy_pi_agent_config(pi_agent_dir)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Unable to prepare subagent: {error}", file=sys.stderr)
        return 1

    events_path = run_dir / "events.jsonl"
    stderr_path = run_dir / "stderr.log"
    command = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--cpus=2",
        "--memory=2g",
        "--pids-limit=512",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--env",
        "HOME=/tmp/pi-home",
        "--mount",
        f"type=bind,source={worktree},target=/workspace",
        "--mount",
        f"type=bind,source={pi_agent_dir},target=/tmp/pi-home/.pi/agent,readonly",
        "--workdir",
        "/workspace",
        args.image,
        "--mode",
        "json",
        "-p",
        "--no-session",
        "--model",
        args.model,
    ]
    if args.thinking:
        command.extend(["--thinking", args.thinking])
    command.append(args.instruction)
    write_metadata(
        run_dir,
        {
            "id": run_id,
            "model": args.model,
            "thinking": args.thinking,
            "instruction": args.instruction,
            "repository": str(repository),
            "base": args.base,
            "branch": branch,
            "worktree": str(worktree),
            "image": args.image,
            "command": command,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    last_message: str | None = None
    with events_path.open("w", encoding="utf-8") as events, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command,
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
    print(f"Branch: {branch}", file=sys.stderr)
    print(f"Worktree: {worktree}", file=sys.stderr)
    print(f"Full event log: {events_path}", file=sys.stderr)
    print(f"Stderr log: {stderr_path}", file=sys.stderr)
    print(f"Clean up with: pi-subagent cleanup {run_id}", file=sys.stderr)

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


def cleanup(args: argparse.Namespace) -> int:
    run_dir = STATE_DIR / args.run
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        print(f"No subagent run found: {args.run}", file=sys.stderr)
        return 1
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    repository = Path(str(metadata["repository"]))
    worktree = Path(str(metadata["worktree"]))
    branch = str(metadata["branch"])
    try:
        subprocess.run(["git", "-C", str(repository), "worktree", "remove", "--force", str(worktree)], check=True)
        subprocess.run(["git", "-C", str(repository), "branch", "--delete", "--force", branch], check=True)
    except subprocess.CalledProcessError as error:
        print(f"Unable to clean up {args.run}: {error}", file=sys.stderr)
        return 1
    print(f"Removed worktree and branch for {args.run}. Retained logs: {run_dir}")
    return 0


def image(args: argparse.Namespace) -> int:
    try:
        ensure_image(args.name)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Docker image ready: {args.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    launch = subcommands.add_parser("run", help="launch a Docker-isolated Pi subagent in a new worktree")
    launch.add_argument("--model", required=True, help="Pi model selector, e.g. openai-codex/gpt-5.6-terra")
    launch.add_argument("--instruction", required=True, help="complete task instruction for the subagent")
    launch.add_argument("--cwd", help="Git repository or path inside it; defaults to the current directory")
    launch.add_argument("--base", default="HEAD", help="Git ref used to create the worktree branch (default: HEAD)")
    launch.add_argument("--image", default=DEFAULT_IMAGE, help=f"Docker image to run (default: {DEFAULT_IMAGE})")
    launch.add_argument(
        "--thinking",
        choices=("off", "minimal", "low", "medium", "high", "xhigh", "max"),
        help="Pi thinking level; omitted uses Pi's configured default",
    )
    launch.add_argument("--confirm-model", action="store_true", help="record that the model and thinking setting were explicitly confirmed")
    launch.set_defaults(handler=run)

    available_models = subcommands.add_parser("models", help="list Pi models available to this host")
    available_models.add_argument("query", nargs="?", help="optional model search string")
    available_models.set_defaults(handler=models)

    review = subcommands.add_parser("inspect", help="print a retained event or stderr log")
    review.add_argument("run", help="run ID printed at launch, or an absolute run directory")
    review.add_argument("--stderr", action="store_true", help="inspect stderr instead of JSON events")
    review.add_argument("--tail", type=int, help="only print the final N lines")
    review.set_defaults(handler=inspect)

    remove = subcommands.add_parser("cleanup", help="remove a completed run's worktree and branch; retain logs")
    remove.add_argument("run", help="run ID printed at launch")
    remove.set_defaults(handler=cleanup)

    build_image = subcommands.add_parser("image", help="build the Docker image if it is absent")
    build_image.add_argument("--name", default=DEFAULT_IMAGE, help=f"image name (default: {DEFAULT_IMAGE})")
    build_image.set_defaults(handler=image)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
