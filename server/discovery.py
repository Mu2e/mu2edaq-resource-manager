"""UDP broadcast discovery for the resource manager.

A client that is not configured with an explicit host/port can broadcast a
discovery datagram; the server replies with the host and port of its HTTP API.

Protocol (UDP):
- Request: a datagram beginning with DISCOVERY_MAGIC.
- Reply:   JSON {"service": "mu2e-resource-manager", "host": <h>, "port": <p>}.
"""

import json
import socket
import sys
import threading
from typing import Optional

DISCOVERY_MAGIC = b"MU2E-RM-DISCOVER-V1"
SERVICE_NAME = "mu2e-resource-manager"
DEFAULT_DISCOVERY_PORT = 8088

# Hosts that are not usable as an advertised address for remote clients.
_NON_ROUTABLE = {"", "0.0.0.0", "::", "0:0:0:0:0:0:0:0", "*"}


def _primary_lan_ip() -> str:
    """Best-effort primary outbound IPv4 address (no packets are sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def resolve_advertise_host(advertise_host: Optional[str], bind_host: Optional[str]) -> str:
    """Pick the address to hand back to clients.

    Priority: explicit advertise_host > a concrete bind host > detected LAN IP.
    """
    if advertise_host:
        return advertise_host
    if bind_host and bind_host not in _NON_ROUTABLE:
        return bind_host
    return _primary_lan_ip()


class DiscoveryResponder(threading.Thread):
    """Daemon thread that answers UDP discovery datagrams."""

    def __init__(
        self,
        http_port: int,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        advertise_host: Optional[str] = None,
        bind_host: str = "0.0.0.0",
    ):
        super().__init__(daemon=True, name="rm-discovery")
        self._http_port = http_port
        self._discovery_port = discovery_port
        self._advertise_host = advertise_host
        self._bind_host = bind_host
        self._sock: Optional[socket.socket] = None
        self._stop = threading.Event()

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", self._discovery_port))
        except OSError as e:
            print(
                f"WARNING: discovery responder could not bind UDP port "
                f"{self._discovery_port}: {e}",
                file=sys.stderr,
            )
            sock.close()
            return
        sock.settimeout(1.0)
        self._sock = sock

        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data.startswith(DISCOVERY_MAGIC):
                continue
            reply = json.dumps(
                {
                    "service": SERVICE_NAME,
                    "host": resolve_advertise_host(self._advertise_host, self._bind_host),
                    "port": self._http_port,
                }
            ).encode()
            try:
                sock.sendto(reply, addr)
            except OSError:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
