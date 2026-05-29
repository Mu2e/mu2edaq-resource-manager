# mu2edaq-resource-manager

The resource manager is a centralized resource reservation service for the Mu2e DAQ system at Fermilab. I based it off of our experiences using a similar resource tracking system for DAQ partitions in NOvA.  It is designed to track both physical hardware resources (DTCs, CFOs, ROCs) as well as software resources (event builders, ports on machines, etc...) that are distributed across DAQ nodes.  The resource manager provides a REST API for clients to reserve and release resources, and provides an API for checking if a resource is available or not.  

The resrouce manager also provides a graphical view of the resource states via a webpage (the original NOvA one was a QT application and maybe I should put in a client is standalone like that too) and allows for some viewing and manual management of resources.

The resource manager is intended to be used in a number of ways.  The most basic is that you can pop up the webpage, set a user name, and reserve/release resources.  The more useful method of using it is through the API which allows applications to check for the availability of a resource, and then reserve it or perform other actions on it.  This means your python or C++ applications (or commandline utils) can interact with the manager.

## Overview

Because our DAQ system uses multiple DAQ processes, running across different nodes, carved up into different partitions, etc...which all need exclusive access to hardware devices, there needs to be a single source of truth and "state keeping" that exists outside of the OTSDAQ instances that can cross-coallate who has what.  This service acts as that single arbiter: clients request resources, the server grants or denies them atomically, and reservations persist across server restarts via a state file.

## Architecture

The design of the system is a simple bottoms up design.  At the bottom there is a configuration file which defines the resources we want to track.

The next level is the atomic reservation system.  This is the layer that does the work of keeping track of the resources and which are available or in use and by who.

The top layer is the API.  The API is intentionally simple.  It provides only a few commands that interact with the reservation layer.

```
┌─────────────────────────────────────────┐
│           REST API (FastAPI)            │  :8080
│  /api/resources  /api/reserve           │
│  /api/release    /api/status            │
└──────────────┬──────────────────────────┘
               │
       ┌───────▼────────┐
       │ ResourceManager │  thread-safe, in-memory
       │  + state.json   │  atomic reservation
       └───────┬─────────┘
               │
       ┌───────▼─────────┐
       │  resources.yaml  │  static hardware config
       └──────────────────┘
```

In terms of interaction with the system there are a number of different methods:

**Clients** can interact via:
- **Python CLI** — `cli/rm_cli.py`
- **C++ client library** — `librmclient` (static, `include/ResourceManagerClient.h`)
- **Web UI** — served at `/` when `web/` is present
- **Direct HTTP** — any HTTP client against the REST API

The Python and C++ libs can be directly included in your applications.  Examples are provided of their use.

The Web based interactions are for human operators (or if you are going through the API endpoints, for Javascript interactions etc...)

## Resource Model

Each resource is identified by a triple: `class:name:enumerator` (e.g., `DTC:CALO-01:01`).

| Field | Description |
|---|---|
| `resource_class` | Hardware type (`DTC`, `CFO`, `ROC`, `EventBuilder`) |
| `name` | Resource name like calo-01 denoting the resource |
| `enumerator` | Instance number (e.g., `01`, `02`) |
| `location.node` | DAQ node hostname |
| `location.user` | Login user on that node |
| `location.ports` | Associated TCP ports (or `ANY` for all ports) |
| `status` | `available` or `reserved` |
| `owner` | Client ID holding the reservation |

## Getting Started

### Installation

The project should be checked out from Git.  EVERYTHING that is needed is contained in this project except for the external dependancies.  These will need to be installed.  There is a bootstrap script that sets up the Python virtual environment and installs the dependencies.

```bash
./scripts/bootstrap.sh
```

This creates a virtual environment in `venv/` and installs everything listed in `requirements.txt`. Re-run it at any time to pull in updated dependencies. Overrides:

- `PYTHON` — interpreter used to create the venv (default: `python3`)
- `RM_VENV` — virtual environment location (default: `venv/`)

The bootstrap script enforces Python 3.9 or newer. To activate the environment in your shell:

```bash
source venv/bin/activate
```

After this the server should run.

**Requirements:** Python 3.9+, `fastapi`, `uvicorn`, `pyyaml`, `requests`, `python-dotenv`

### Server

There are scripts that start and stop the server. Use them so that resources are handled correctly and so that a daemon-mode server is shut down properly.

Start in the foreground (Ctrl-C to stop):

```bash
./scripts/start_server.sh
```

Start in the background as a daemon (writes a PID file):

```bash
./scripts/start_server.sh --daemon      # or: -d, or set RM_DAEMON=1
```

In daemon mode the PID is written to `run/resource-manager.pid` and output is logged to `run/resource-manager.log`. Starting a second daemon while one is already running is refused. Stop the daemon with:

```bash
./scripts/stop_server.sh
```

The stop script sends `SIGTERM` for a graceful shutdown and escalates to `SIGKILL` if the process has not exited within `RM_STOP_TIMEOUT` seconds (default 10), then removes the PID file.

Any extra arguments to the start script are forwarded to `server/mu2e-resource-manager.py` and override the environment-derived values (commandline wins):

```bash
./scripts/start_server.sh --port 9000
```

You can also run the server module directly:

```bash
python3 server/mu2e-resource-manager.py --host 127.0.0.1 --port 8080 \
    --config config/resources.yaml \
    --state config/state.json \
    --auth-config config/auth.yaml
```

The server binds to `127.0.0.1` (localhost) by default; set `--host 0.0.0.0` (or `RM_HOST=0.0.0.0`) to expose it on all interfaces, which should only be done with authentication configured (see [Authentication](#authentication)).

**Environment variables:** `RM_HOST`, `RM_PORT`, `RM_CONFIG`, `RM_STATE`, `RM_AUTH_CONFIG`, `RM_AUTH_DISABLED`, `RM_DISCOVERY`, `RM_DISCOVERY_PORT`, `RM_ADVERTISE_HOST`, `RM_DAEMON`, `RM_RUN_DIR`, `RM_PIDFILE`, `RM_LOG`, `RM_STOP_TIMEOUT`, `RM_VENV`. These can be set in your shell or placed in a `.env` file (see [Configuration](#configuration)).

### Python CLI

```bash
# List all resources
python3 cli/rm_cli.py list

# Filter by status
python3 cli/rm_cli.py list --status available

# Get a specific resource
python3 cli/rm_cli.py get DTC DTC 01

# Reserve resources (all-or-nothing). Reserve/release/release-all require a
# token; pass --token or set RM_TOKEN. The owner is the token's principal.
python3 cli/rm_cli.py --token "$RM_TOKEN" reserve DTC DTC 01
python3 cli/rm_cli.py --token "$RM_TOKEN" reserve DTC DTC 01 CFO CFO 01

# Optionally annotate the reservation with an operator label (the "Who" column)
python3 cli/rm_cli.py --token "$RM_TOKEN" reserve --who Andrew DTC DTC 01

# Release resources
python3 cli/rm_cli.py --token "$RM_TOKEN" release DTC DTC 01

# Release all resources held by a client (operators may target any client)
python3 cli/rm_cli.py --token "$RM_TOKEN" release-all partition1

# Server summary
python3 cli/rm_cli.py status
```

Use `--host` / `--port` to target a remote server, and `--token` (or the `RM_TOKEN` environment variable) for state-changing commands. Read-only commands (`list`, `get`, `status`) need no token. The `reserve` command accepts an optional `--who` (or `RM_WHO`) operator annotation shown in the "Who" column. The C++ CLI (`rm-cli`) takes the same `--token` / `--who` options.

When `--host` is **not** given (and `RM_HOST` is unset), the CLI locates the server via UDP broadcast discovery and routes to the host/port it returns (see [Discovery](#discovery)); pass `--no-discover` to skip this and fall back to `localhost:8080`.

### C++ Client Library

**Requirements:** CMake 3.14+, libcurl, C++17 compiler

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

This produces:
- `librmclient.a` — static client library
- `rm-cli` — C++ CLI binary
- `rm-demo` — demonstration program

**Usage in C++:**

```cpp
#include "ResourceManagerClient.h"

mu2e::ResourceManagerClient client("mu2edaq-server.fnal.gov", 8080);

// Reserve a DTC
auto result = client.reserve("my-process", {{"DTC", "DTC", "01"}});
if (result.success) {
    // use the resource...
    client.releaseAll("my-process");
}
```

## Configuration

Configuration is resolved with the following priority (highest first):

1. Commandline flags (e.g. `--port`)
2. Environment variables (e.g. `RM_PORT`)
3. A `.env` file in the project root
4. The `config/resources.yaml` file (for resource definitions)
5. Built-in defaults

### `.env`

Both the shell scripts and the server read a `.env` file in the project root, if present. Copy the template and edit it:

```bash
cp example.env .env
```

`example.env` documents every supported variable (`RM_HOST`, `RM_PORT`, `RM_CONFIG`, `RM_STATE`, `RM_AUTH_CONFIG`, `RM_AUTH_DISABLED`, `RM_TOKEN`, `RM_WHO`, `RM_DISCOVERY`, `RM_DISCOVERY_PORT`, `RM_ADVERTISE_HOST`, `RM_DAEMON`, `RM_RUN_DIR`, `RM_PIDFILE`, `RM_LOG`, `RM_STOP_TIMEOUT`, `PYTHON`, `RM_VENV`). A variable already set in your shell environment takes precedence over the value in `.env`, so `.env` acts as a per-checkout default. The `.env` file is git-ignored; `example.env` is the committed template.

### Authentication

The state-changing endpoints (`POST /api/reserve`, `POST /api/release`, `DELETE /api/clients/{id}/resources`) require a bearer token; read-only endpoints (`GET /api/resources`, `GET /api/status`) are open. Tokens map to a **principal** (the identity that owns reservations) and a **role**:

- `client` — may reserve, and release/release-all only its own resources.
- `operator` — may release any resource and release-all for any client.

Configure tokens by copying the template (the live file is git-ignored):

```bash
cp config/auth.example.yaml config/auth.yaml
```

```yaml
auth:
  tokens:
    - token: "a-long-random-secret"
      principal: partition1
      role: client
    - token: "an-operator-secret"
      principal: operator
      role: operator
```

Clients send the token as `Authorization: Bearer <token>`. The owner of a reservation is always the authenticated principal — the `client_id` field in request bodies is ignored for authorization. Override the config path with `RM_AUTH_CONFIG`.

If no tokens are configured the server still runs but rejects every state-changing request with `401`. For a trusted, localhost-only deployment you can disable auth entirely with `RM_AUTH_DISABLED=1` (do not do this on an interface reachable beyond localhost).

### Discovery

So clients don't need a hardcoded address, the server runs a small **UDP broadcast discovery** responder (enabled by default). A client with no configured host broadcasts a discovery datagram on the discovery port; the server replies with the host and port of its HTTP API, and the client routes its requests there.

```
client (no --host)  ──UDP broadcast :8088──▶  server discovery responder
client              ◀──{host, port} reply───  server
client ──HTTP──▶ host:port  (normal API calls, with token as needed)
```

- **Discovery port:** UDP `8088` by default (`--discovery-port` / `RM_DISCOVERY_PORT`); HTTP stays on TCP `8080`. Server and client must agree on the discovery port.
- **Advertised host:** the server reports `--advertise-host` / `RM_ADVERTISE_HOST` if set; otherwise a concrete `--host`; otherwise its auto-detected primary LAN IP. Set `--advertise-host` explicitly when binding `0.0.0.0` on a multi-homed host.
- **Disable:** `--no-discovery` / `RM_DISCOVERY=0` on the server; `--no-discover` on a client.
- Discovery only returns the endpoint location — the HTTP API is still protected by [Authentication](#authentication).

Python and C++ clients discover automatically when no host is configured; you can also call discovery directly: `ResourceManagerClient::discover()` (C++) or the `discover()` helper in `cli/rm_cli.py` (Python).

### `config/resources.yaml`

Defines the static set of hardware resources. Edit this file to add or remove resources; restart the server to apply changes.

```yaml
resources:
  - class: DTC
    name: DTC
    enumerator: "01"
    location:
      node: mu2edaq01.fnal.gov
      user: mu2edaq
      ports: [2000, 2001, 2002]

  - class: EventBuilder
    name: EB
    enumerator: "01"
    location:
      node: mu2edaq03.fnal.gov
      user: mu2edaq
      ports: ANY            # all ports — displayed as "ANY"
```

`ports` is a list of TCP port numbers, or the literal `ANY` (case-insensitive) meaning the resource uses all ports. `ANY` is shown as `ANY` in the listings and exposed in the API as `ports: []` with `ports_any: true`.

### `config/state.json`

Written automatically by the server to persist reservations across restarts. Do not edit by hand. This file is excluded from version control.

## REST API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/resources` | — | List all resources (`?status=available\|reserved`) |
| `GET` | `/api/resources/{class}/{name}/{enum}` | — | Get a specific resource |
| `POST` | `/api/reserve` | Bearer | Reserve resources (all-or-nothing; owner = principal) |
| `POST` | `/api/release` | Bearer | Release resources (own only; operator: any) |
| `DELETE` | `/api/clients/{client_id}/resources` | Bearer | Release all resources for a client (own only; operator: any) |
| `GET` | `/api/status` | — | Server summary (total/available/reserved counts) |
| `GET` | `/api/whoami` | Bearer | Return the authenticated principal and role for the token |

Endpoints marked **Bearer** require an `Authorization: Bearer <token>` header (see [Authentication](#authentication)). At least one resource is required in reserve/release request bodies; an empty list returns `422`.

Interactive API docs are available at `http://localhost:8080/docs` when the server is running.

## Testing

```bash
# Python API/auth tests (pytest)
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest tests/

# C++ client lifecycle test (CTest)
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
(cd build && ctest --output-on-failure)
```
