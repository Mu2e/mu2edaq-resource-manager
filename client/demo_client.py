#!/usr/bin/env python3
"""
Mu2e DAQ Resource Manager — Python Demo Client

Demonstrates a typical client workflow:
  1. Check server status
  2. List all resources
  3. List available resources
  4. Reserve resources
  5. Attempt conflicting reservation (expect error)
  6. Attempt reservation of non-existent resource (expect error)
  7. Show current state
  8. Release reserved resources
  9. Confirm final state
"""

import sys
import requests

BASE_URL  = "http://localhost:8080"
CLIENT_ID = "python-demo-client"

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"


def section(n: int, title: str):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD} Step {n}: {title}{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")


def print_resource(r: dict):
    ports = ",".join(str(p) for p in r.get("location", {}).get("ports", []))
    status_colored = f"{GREEN}{r['status']}{RESET}" if r["status"] == "available" else f"{RED}{r['status']}{RESET}"
    owner = f"  {DIM}owned by {YELLOW}{r['owner']}{RESET}" if r.get("owner") else ""
    print(
        f"  {r['resource_class']}:{r['name']}:{r['enumerator']}"
        f"  @  {r['location']['node']}  [{ports}]"
        f"  →  {status_colored}{owner}"
    )


def get_resources(status=None):
    params = {"status": status} if status else {}
    r = requests.get(f"{BASE_URL}/api/resources", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def reserve(client_id: str, resources: list):
    return requests.post(
        f"{BASE_URL}/api/reserve",
        json={"client_id": client_id, "resources": resources},
        timeout=10,
    )


def release(client_id: str, resources: list):
    return requests.post(
        f"{BASE_URL}/api/release",
        json={"client_id": client_id, "resources": resources},
        timeout=10,
    )


def main():
    global BASE_URL
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1].rstrip("/")

    print(f"\n{BOLD}Mu2e DAQ Resource Manager — Python Demo Client{RESET}")
    print(f"Server:    {BASE_URL}")
    print(f"Client ID: {CLIENT_ID}")

    # ── 1. Server status ──────────────────────────────────────────────────
    section(1, "Server Status")
    try:
        s = requests.get(f"{BASE_URL}/api/status", timeout=10).json()
    except requests.ConnectionError:
        print(f"{RED}Cannot connect to {BASE_URL}. Is the server running?{RESET}")
        sys.exit(1)
    print(
        f"  Total: {s['total']}  |  "
        f"Available: {GREEN}{s['available']}{RESET}  |  "
        f"Reserved: {RED}{s['reserved']}{RESET}"
    )

    # ── 2. All resources ──────────────────────────────────────────────────
    section(2, "All Resources")
    all_resources = get_resources()
    for r in all_resources:
        print_resource(r)

    # ── 3. Available resources ────────────────────────────────────────────
    section(3, "Available Resources")
    available = get_resources(status="available")
    if not available:
        print(f"  {RED}No available resources — nothing to reserve.{RESET}")
        sys.exit(0)
    for r in available:
        print_resource(r)

    # ── 4. Reserve first two available resources ──────────────────────────
    section(4, "Reserving Resources")
    to_reserve = [
        {"resource_class": r["resource_class"], "name": r["name"], "enumerator": r["enumerator"]}
        for r in available[: min(2, len(available))]
    ]
    print(f"  Requesting {len(to_reserve)} resource(s) for '{CLIENT_ID}':")
    for tr in to_reserve:
        print(f"    → {tr['resource_class']}:{tr['name']}:{tr['enumerator']}")

    resp = reserve(CLIENT_ID, to_reserve)
    if resp.status_code == 200:
        data = resp.json()
        print(f"\n  {GREEN}✓ {data['message']}{RESET}")
        for r in data["resources"]:
            print_resource(r)
    else:
        print(f"\n  {RED}✗ Unexpected failure: {resp.json()}{RESET}")
        sys.exit(1)

    # ── 5. Attempt double-reservation ─────────────────────────────────────
    section(5, "Attempting Double-Reservation (Expected Error)")
    conflict_client = "another-client"
    print(f"  Trying to reserve {to_reserve[0]['resource_class']}:{to_reserve[0]['name']}:{to_reserve[0]['enumerator']}")
    print(f"  as client '{conflict_client}'")

    resp = reserve(conflict_client, [to_reserve[0]])
    if resp.status_code == 409:
        detail = resp.json().get("detail", {})
        print(f"\n  {RED}✓ Got expected 409 error:{RESET}")
        print(f"    {detail.get('message', '?')}")
        for r in detail.get("resources", []):
            print_resource(r)
    else:
        print(f"  {YELLOW}Unexpected response: {resp.status_code}{RESET}")

    # ── 6. Attempt non-existent resource ──────────────────────────────────
    section(6, "Attempting Non-Existent Resource (Expected Error)")
    bogus = [{"resource_class": "BOGUS", "name": "FAKE", "enumerator": "99"}]
    print("  Requesting: BOGUS:FAKE:99")

    resp = reserve(CLIENT_ID, bogus)
    if resp.status_code == 409:
        msg = resp.json().get("detail", {}).get("message", "?")
        print(f"\n  {RED}✓ Got expected error:{RESET} {msg}")
    else:
        print(f"  {YELLOW}Unexpected response: {resp.status_code}{RESET}")

    # ── 7. Current state ──────────────────────────────────────────────────
    section(7, "Current Resource State (Mixed)")
    for r in get_resources():
        print_resource(r)

    # ── 8. Release resources ──────────────────────────────────────────────
    section(8, "Releasing Reserved Resources")
    for tr in to_reserve:
        print(f"  Releasing {tr['resource_class']}:{tr['name']}:{tr['enumerator']}")

    resp = release(CLIENT_ID, to_reserve)
    if resp.status_code == 200:
        print(f"\n  {GREEN}✓ {resp.json()['message']}{RESET}")
    else:
        print(f"\n  {RED}✗ Release failed: {resp.json().get('detail')}{RESET}")

    # ── 9. Final state ────────────────────────────────────────────────────
    section(9, "Final Resource State")
    for r in get_resources():
        print_resource(r)

    s = requests.get(f"{BASE_URL}/api/status", timeout=10).json()
    print(
        f"\n  {BOLD}Final Status:{RESET}  Total: {s['total']}  |  "
        f"Available: {GREEN}{s['available']}{RESET}  |  "
        f"Reserved: {RED}{s['reserved']}{RESET}"
    )
    print(f"\n{GREEN}Demo complete.{RESET}\n")


if __name__ == "__main__":
    main()
