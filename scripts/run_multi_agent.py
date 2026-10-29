"""Launch only the multi-agent ADK app, optionally with a different Ollama chat model.

Run from any directory with the project environment activated, for example:
    python scripts/run_multi_agent.py --model llama3.1:8b --port 8001
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = PROJECT_ROOT / "src"
DEFAULT_MODEL = "qwen3:8b"


def valid_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--model",
        help="Ollama chat model tag for the multi-agent app (for example llama3.1:8b).",
    )
    parser.add_argument("--port", type=valid_port, default=8001, help="ADK web port (default: 8001).")
    args = parser.parse_args()

    adk_cli = shutil.which("adk")
    if not adk_cli:
        parser.error("Could not find the 'adk' command. Activate the project environment (as_env) first.")

    env = os.environ.copy()
    model = (
        args.model
        or env.get("HELPDESK_MULTI_CHAT_MODEL")
        or env.get("HELPDESK_CHAT_MODEL")
        or DEFAULT_MODEL
    )
    env["HELPDESK_MULTI_CHAT_MODEL"] = model

    command = [adk_cli, "web", "--port", str(args.port), "academic_helpdesk_multi"]
    print(f"Multi-agent chat model: {model}", flush=True)
    print(f"Opening ADK web at http://127.0.0.1:{args.port}", flush=True)
    return subprocess.run(command, cwd=AGENTS_ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
