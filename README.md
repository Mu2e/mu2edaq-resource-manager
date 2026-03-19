# mu2edaq-resource-manager

A centralized resource reservation service for the Mu2e DAQ system at Fermilab. It tracks hardware resources (DTCs, CFOs, ROCs, EventBuilders) distributed across DAQ nodes and provides a REST API for clients to reserve and release them.

## Overview

Multiple DAQ processes running across different nodes need exclusive access to shared hardware. This service acts as a single arbiter: clients request resources, the server grants or denies them atomically, and reservations persist across server restarts via a state file.

## Architecture

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

**Clients** can interact via:
- **Python CLI** — `cli/rm_cli.py`
- **C++ client library** — `librmclient` (static, `include/ResourceManagerClient.h`)
- **Web UI** — served at `/` when `web/` is present
- **Direct HTTP** — any HTTP client against the REST API

## Resource Model

Each resource is identified by a triple: `class:name:enumerator` (e.g., `DTC:DTC:01`).

| Field | Description |
|---|---|
| `resource_class` | Hardware type (`DTC`, `CFO`, `ROC`, `EventBuilder`) |
| `name` | Resource name |
| `enumerator` | Instance number (e.g., `01`, `02`) |
| `location.node` | DAQ node hostname |
| `location.user` | Login user on that node |
| `location.ports` | Associated TCP ports |
| `status` | `available` or `reserved` |
| `owner` | Client ID holding the reservation |

## Getting Started

### Server

**Requirements:** Python 3.10+, `fastapi`, `uvicorn`, `pyyaml`

```bash
pip install -r requirements.txt
./scripts/start_server.sh
```

Or with custom options:

```bash
python3 server/app.py --host 0.0.0.0 --port 8080 \
    --config config/resources.yaml \
    --state config/state.json
```

Environment variables: `RM_HOST`, `RM_PORT`, `RM_CONFIG`, `RM_STATE`

### Python CLI

```bash
# List all resources
python3 cli/rm_cli.py list

# Filter by status
python3 cli/rm_cli.py list --status available

# Get a specific resource
python3 cli/rm_cli.py get DTC DTC 01

# Reserve resources (all-or-nothing)
python3 cli/rm_cli.py reserve my-client DTC DTC 01
python3 cli/rm_cli.py reserve my-client DTC DTC 01 CFO CFO 01

# Release resources
python3 cli/rm_cli.py release my-client DTC DTC 01

# Release all resources held by a client
python3 cli/rm_cli.py release-all my-client

# Server summary
python3 cli/rm_cli.py status
```

Use `--host` / `--port` to target a remote server (default: `localhost:8080`).

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
```

### `config/state.json`

Written automatically by the server to persist reservations across restarts. Do not edit by hand. This file is excluded from version control.

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/resources` | List all resources (`?status=available\|reserved`) |
| `GET` | `/api/resources/{class}/{name}/{enum}` | Get a specific resource |
| `POST` | `/api/reserve` | Reserve resources (all-or-nothing) |
| `POST` | `/api/release` | Release resources |
| `DELETE` | `/api/clients/{client_id}/resources` | Release all resources for a client |
| `GET` | `/api/status` | Server summary (total/available/reserved counts) |

Interactive API docs are available at `http://localhost:8080/docs` when the server is running.
