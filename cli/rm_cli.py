#!/usr/bin/env python3
"""Mu2e DAQ Resource Manager — Command Line Interface"""

import argparse
import json
import os
import socket
import sys

import requests

# ── UDP broadcast discovery ───────────────────────────────────────────────────
# Must match server/discovery.py.
DISCOVERY_MAGIC = b"MU2E-RM-DISCOVER-V1"
DISCOVERY_SERVICE = "mu2e-resource-manager"
DEFAULT_DISCOVERY_PORT = 8088


def discover(discovery_port: int, timeout: float = 2.0):
    """Broadcast a discovery request; return (host, port) or None on timeout."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(DISCOVERY_MAGIC, ("255.255.255.255", discovery_port))
        while True:
            try:
                data, _ = sock.recvfrom(1024)
            except socket.timeout:
                return None
            try:
                msg = json.loads(data.decode())
            except (ValueError, UnicodeDecodeError):
                continue
            if msg.get("service") == DISCOVERY_SERVICE and "host" in msg and "port" in msg:
                return msg["host"], int(msg["port"])
    except OSError:
        return None
    finally:
        sock.close()

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
        f"{'NODE':<28} {'USER':<14} {'PORTS':<22} STATUS / OWNER / WHO"
        f"{RESET}"
    )
    print("  " + "─" * 110)


def _print_resource(r: dict):
    ports = ",".join(str(p) for p in r.get("location", {}).get("ports", []))
    owner = r.get("owner") or ""
    who = r.get("who") or ""
    owner_str = f"  ({YELLOW}{owner}{RESET})" if owner else ""
    who_str = f"  [{YELLOW}{who}{RESET}]" if who else ""
    print(
        f"  {r['resource_class']:<14} {r['name']:<12} {r['enumerator']:<6} "
        f"{r['location']['node']:<28} {r['location']['user']:<14} "
        f"{ports:<22} {_status_str(r['status'])}{owner_str}{who_str}"
    )


class CLI:
    def __init__(self, host: str, port: int, token: str = None):
        self.base = f"http://{host}:{port}"
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def _get(self, path, params=None):
        r = requests.get(f"{self.base}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _post(self, path, payload):
        return requests.post(f"{self.base}{path}", json=payload, headers=self._headers, timeout=10)

    def _delete(self, path):
        r = requests.delete(f"{self.base}{path}", headers=self._headers, timeout=10)
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
        payload = {"who": args.who, "resources": resources}
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
        payload = {"resources": resources}
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
  %(prog)s reserve DTC DTC 01
  %(prog)s reserve --who Andrew DTC DTC 01 CFO CFO 01
  %(prog)s release DTC DTC 01
  %(prog)s release-all partition1
  %(prog)s status
""",
    )
    _env_port = os.environ.get("RM_PORT")
    parser.add_argument(
        "--host",
        default=os.environ.get("RM_HOST"),
        help="Server host. If unset, the server is located via broadcast discovery.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(_env_port) if _env_port else None,
        help="Server port (default: discovered, else 8080)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("RM_TOKEN"),
        help="Bearer token for reserve/release (or set RM_TOKEN)",
    )
    parser.add_argument(
        "--discovery-port",
        type=int,
        default=int(os.environ.get("RM_DISCOVERY_PORT", DEFAULT_DISCOVERY_PORT)),
        help=f"UDP discovery port (default: {DEFAULT_DISCOVERY_PORT})",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Do not attempt broadcast discovery when --host is unset",
    )

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

    # reserve (owner is the authenticated token principal)
    p_res = sub.add_parser("reserve", help="Reserve resources")
    p_res.add_argument("resources", nargs="+", metavar="CLASS NAME ENUM",
                       help="One or more triples: <class> <name> <enumerator>")
    p_res.add_argument("--who", default=os.environ.get("RM_WHO"),
                       help="Optional operator annotation shown in the 'Who' column (or set RM_WHO)")

    # release (authorized against the token principal)
    p_rel = sub.add_parser("release", help="Release resources")
    p_rel.add_argument("resources", nargs="+", metavar="CLASS NAME ENUM")

    # release-all (CLIENT_ID is the target; operators may target any client)
    p_ra = sub.add_parser("release-all", help="Release all resources for a client")
    p_ra.add_argument("client_id", metavar="CLIENT_ID")

    # status
    sub.add_parser("status", help="Show server status")

    args = parser.parse_args()

    # Resolve the endpoint: explicit --host/RM_HOST wins; otherwise discover.
    host, port = args.host, args.port
    if host is None and not args.no_discover:
        found = discover(args.discovery_port)
        if found:
            host, discovered_port = found
            if port is None:
                port = discovered_port
            print(f"{YELLOW}Discovered resource manager at {host}:{port}{RESET}", file=sys.stderr)
        else:
            print(f"{YELLOW}Discovery found no server; falling back to localhost.{RESET}", file=sys.stderr)
    if host is None:
        host = "localhost"
    if port is None:
        port = 8080

    cli = CLI(host, port, token=args.token)

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
