#!/usr/bin/env python3
"""Mu2e DAQ Resource Manager — Command Line Interface"""

import argparse
import sys

import requests

# ANSI colours (disabled when not a tty)
_TTY = sys.stdout.isatty()
GREEN  = "\033[32m" if _TTY else ""
RED    = "\033[31m" if _TTY else ""
YELLOW = "\033[33m" if _TTY else ""
BOLD   = "\033[1m"  if _TTY else ""
RESET  = "\033[0m"  if _TTY else ""


def _status_str(status: str) -> str:
    if status == "available":
        return f"{GREEN}{status}{RESET}"
    if status == "reserved":
        return f"{RED}{status}{RESET}"
    return status


def _print_header():
    print(
        f"\n{BOLD}"
        f"  {'CLASS':<14} {'NAME':<12} {'#':<6} "
        f"{'NODE':<28} {'USER':<14} {'PORTS':<22} STATUS / OWNER"
        f"{RESET}"
    )
    print("  " + "─" * 110)


def _print_resource(r: dict):
    ports = ",".join(str(p) for p in r.get("location", {}).get("ports", []))
    owner = r.get("owner") or ""
    owner_str = f"  ({YELLOW}{owner}{RESET})" if owner else ""
    print(
        f"  {r['resource_class']:<14} {r['name']:<12} {r['enumerator']:<6} "
        f"{r['location']['node']:<28} {r['location']['user']:<14} "
        f"{ports:<22} {_status_str(r['status'])}{owner_str}"
    )


class CLI:
    def __init__(self, host: str, port: int):
        self.base = f"http://{host}:{port}"

    def _get(self, path, params=None):
        r = requests.get(f"{self.base}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path, payload):
        return requests.post(f"{self.base}{path}", json=payload, timeout=10)

    def _delete(self, path):
        r = requests.delete(f"{self.base}{path}", timeout=10)
        r.raise_for_status()
        return r.json()

    # ── Commands ────────────────────────────────────────────────────────────

    def cmd_list(self, args):
        params = {"status": args.status} if args.status else {}
        resources = self._get("/api/resources", params=params)
        _print_header()
        for r in resources:
            _print_resource(r)
        total = len(resources)
        print(f"\n  {total} resource(s) shown.\n")

    def cmd_get(self, args):
        try:
            r = self._get(f"/api/resources/{args.resource_class}/{args.name}/{args.enumerator}")
            _print_header()
            _print_resource(r)
            print()
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                print(
                    f"{RED}Not found: {args.resource_class}:{args.name}:{args.enumerator}{RESET}",
                    file=sys.stderr,
                )
                sys.exit(1)
            raise

    def cmd_reserve(self, args):
        resources = _parse_triples(args.resources)
        payload = {"client_id": args.client_id, "resources": resources}
        r = self._post("/api/reserve", payload)
        if r.status_code == 200:
            data = r.json()
            print(f"{GREEN}✓ {data['message']}{RESET}")
            _print_header()
            for res in data["resources"]:
                _print_resource(res)
            print()
        else:
            detail = r.json().get("detail", {})
            if isinstance(detail, dict):
                print(f"{RED}✗ {detail.get('message', 'Unknown error')}{RESET}", file=sys.stderr)
                conflicting = detail.get("resources", [])
                if conflicting:
                    print("Conflicting resource(s):")
                    _print_header()
                    for res in conflicting:
                        _print_resource(res)
                    print()
            else:
                print(f"{RED}✗ {detail}{RESET}", file=sys.stderr)
            sys.exit(1)

    def cmd_release(self, args):
        resources = _parse_triples(args.resources)
        payload = {"client_id": args.client_id, "resources": resources}
        r = self._post("/api/release", payload)
        if r.status_code == 200:
            print(f"{GREEN}✓ {r.json()['message']}{RESET}")
        else:
            print(f"{RED}✗ {r.json().get('detail', 'Unknown error')}{RESET}", file=sys.stderr)
            sys.exit(1)

    def cmd_release_all(self, args):
        data = self._delete(f"/api/clients/{args.client_id}/resources")
        print(f"{GREEN}✓ {data['message']}{RESET}")

    def cmd_status(self, args):
        s = self._get("/api/status")
        print(f"\n{BOLD}Server Status{RESET}")
        print(f"  Total:     {s['total']}")
        print(f"  Available: {GREEN}{s['available']}{RESET}")
        print(f"  Reserved:  {RED}{s['reserved']}{RESET}\n")


def _parse_triples(tokens: list) -> list:
    if len(tokens) % 3 != 0:
        print(
            f"{RED}Error: resources must be given as triples: <class> <name> <enumerator>{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)
    return [
        {"resource_class": tokens[i], "name": tokens[i + 1], "enumerator": tokens[i + 2]}
        for i in range(0, len(tokens), 3)
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Mu2e DAQ Resource Manager CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list
  %(prog)s list --status available
  %(prog)s get DTC DTC 01
  %(prog)s reserve my-client DTC DTC 01
  %(prog)s reserve my-client DTC DTC 01 CFO CFO 01
  %(prog)s release my-client DTC DTC 01
  %(prog)s release-all my-client
  %(prog)s status
""",
    )
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080)")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # list
    p_list = sub.add_parser("list", help="List resources")
    p_list.add_argument("--status", choices=["available", "reserved"], help="Filter by status")

    # get
    p_get = sub.add_parser("get", help="Get a specific resource")
    p_get.add_argument("resource_class", metavar="CLASS")
    p_get.add_argument("name", metavar="NAME")
    p_get.add_argument("enumerator", metavar="ENUM")

    # reserve
    p_res = sub.add_parser("reserve", help="Reserve resources")
    p_res.add_argument("client_id", metavar="CLIENT_ID")
    p_res.add_argument("resources", nargs="+", metavar="CLASS NAME ENUM",
                       help="One or more triples: <class> <name> <enumerator>")

    # release
    p_rel = sub.add_parser("release", help="Release resources")
    p_rel.add_argument("client_id", metavar="CLIENT_ID")
    p_rel.add_argument("resources", nargs="+", metavar="CLASS NAME ENUM")

    # release-all
    p_ra = sub.add_parser("release-all", help="Release all resources for a client")
    p_ra.add_argument("client_id", metavar="CLIENT_ID")

    # status
    sub.add_parser("status", help="Show server status")

    args = parser.parse_args()
    cli = CLI(args.host, args.port)

    dispatch = {
        "list": cli.cmd_list,
        "get": cli.cmd_get,
        "reserve": cli.cmd_reserve,
        "release": cli.cmd_release,
        "release-all": cli.cmd_release_all,
        "status": cli.cmd_status,
    }

    try:
        dispatch[args.command](args)
    except requests.ConnectionError:
        print(f"{RED}Cannot connect to server at {cli.base}{RESET}", file=sys.stderr)
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"{RED}HTTP error {e.response.status_code}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
