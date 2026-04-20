"""CLI entry for the SOP MCP server.

Usage:
    python -m superagent.sop_mcp_server              # speak MCP stdio
    python -m superagent.sop_mcp_server --list       # list SOP slugs
    python -m superagent.sop_mcp_server --show SLUG  # print one SOP body
"""

from __future__ import annotations

import argparse
import sys

from .server import SOP_DIR, build_server, iter_sops


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="superagent.sop_mcp_server")
    parser.add_argument("--list", action="store_true", help="list available SOP slugs")
    parser.add_argument("--show", metavar="SLUG", help="print one SOP body")
    args = parser.parse_args(argv)

    if args.list:
        for slug, _path in iter_sops():
            print(slug)
        return 0

    if args.show:
        for slug, path in iter_sops():
            if slug == args.show:
                sys.stdout.write(path.read_text(encoding="utf-8"))
                return 0
        print(f"unknown SOP slug: {args.show}", file=sys.stderr)
        return 2

    server = build_server(SOP_DIR)
    server.run()  # stdio by default
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
