"""Deploy the readiness diagnostic to AgentCore Runtime behind inbound OAuth, and prove it.

    python3 -m deploy.agentcore deploy     create or update everything (idempotent)
    python3 -m deploy.agentcore demo       call without a token (rejected) and with one (accepted)
    python3 -m deploy.agentcore destroy    delete everything deploy created
    python3 -m deploy.agentcore package    only build the zip (no AWS calls)

See deploy/agentcore/README.md.
"""
from __future__ import annotations

import argparse
import sys

from . import demo, package, provision
from .settings import State


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m deploy.agentcore", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["deploy", "demo", "destroy", "package"])
    args = parser.parse_args(argv)

    if args.command == "package":
        print(package.build())
        return 0
    if args.command == "deploy":
        provision.deploy()
        return 0
    if args.command == "destroy":
        provision.destroy()
        return 0
    state = State.load()
    if state is None or not state.runtime_arn:
        print("No deployed runtime found. Run: python3 -m deploy.agentcore deploy", file=sys.stderr)
        return 2
    return 0 if demo.run(state) else 1


if __name__ == "__main__":
    raise SystemExit(main())
