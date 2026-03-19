import json
import os
import threading
import yaml
from typing import Dict, List, Optional, Tuple

from models import Location, Resource, ResourceIdentifier


class ResourceManager:
    def __init__(self, config_file: str, state_file: Optional[str] = None):
        self._lock = threading.Lock()
        self._resources: Dict[str, Resource] = {}
        self._state_file = state_file
        self._load_config(config_file)
        if state_file:
            self._load_state(state_file)

    @staticmethod
    def _resource_key(resource_class: str, name: str, enumerator: str) -> str:
        return f"{resource_class}:{name}:{enumerator}"

    def _load_config(self, config_file: str):
        with open(config_file) as f:
            config = yaml.safe_load(f)
        for r in config.get("resources", []):
            loc = r["location"]
            location = Location(
                node=loc["node"],
                user=loc["user"],
                ports=loc.get("ports", []),
            )
            resource = Resource(
                resource_class=r["class"],
                name=r["name"],
                enumerator=str(r["enumerator"]),
                location=location,
            )
            key = self._resource_key(resource.resource_class, resource.name, resource.enumerator)
            self._resources[key] = resource

    def _load_state(self, state_file: str):
        if not os.path.exists(state_file):
            return
        try:
            with open(state_file) as f:
                state = json.load(f)
            for key, entry in state.items():
                if key in self._resources:
                    self._resources[key].status = entry.get("status", "available")
                    self._resources[key].owner = entry.get("owner")
        except (json.JSONDecodeError, KeyError):
            pass  # corrupt state file — start fresh

    def _save_state(self):
        if not self._state_file:
            return
        state = {
            key: {"status": r.status, "owner": r.owner}
            for key, r in self._resources.items()
        }
        tmp = self._state_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, self._state_file)

    def list_resources(self, status: Optional[str] = None) -> List[Resource]:
        with self._lock:
            resources = list(self._resources.values())
        if status:
            resources = [r for r in resources if r.status == status]
        return resources

    def get_resource(self, resource_class: str, name: str, enumerator: str) -> Optional[Resource]:
        key = self._resource_key(resource_class, name, enumerator)
        with self._lock:
            return self._resources.get(key)

    def reserve_resources(
        self, client_id: str, identifiers: List[ResourceIdentifier]
    ) -> Tuple[bool, str, List[Resource]]:
        with self._lock:
            # Validate all resources exist and are available before touching any
            for ident in identifiers:
                key = self._resource_key(ident.resource_class, ident.name, ident.enumerator)
                resource = self._resources.get(key)
                if resource is None:
                    return False, f"Resource '{key}' does not exist", []
                if resource.status == "reserved":
                    return (
                        False,
                        f"Resource '{key}' is already reserved by '{resource.owner}'",
                        [resource],
                    )

            # All checks passed — reserve atomically
            reserved = []
            for ident in identifiers:
                key = self._resource_key(ident.resource_class, ident.name, ident.enumerator)
                self._resources[key].status = "reserved"
                self._resources[key].owner = client_id
                reserved.append(self._resources[key])

            self._save_state()
            return True, f"Successfully reserved {len(reserved)} resource(s)", reserved

    def release_resources(
        self, client_id: str, identifiers: List[ResourceIdentifier]
    ) -> Tuple[bool, str]:
        with self._lock:
            # Validate all before releasing any
            for ident in identifiers:
                key = self._resource_key(ident.resource_class, ident.name, ident.enumerator)
                resource = self._resources.get(key)
                if resource is None:
                    return False, f"Resource '{key}' does not exist"
                if resource.status == "available":
                    return False, f"Resource '{key}' is not currently reserved"
                if resource.owner != client_id:
                    return False, f"Resource '{key}' is owned by '{resource.owner}', not '{client_id}'"

            for ident in identifiers:
                key = self._resource_key(ident.resource_class, ident.name, ident.enumerator)
                self._resources[key].status = "available"
                self._resources[key].owner = None

            self._save_state()
            return True, f"Successfully released {len(identifiers)} resource(s)"

    def release_all_for_client(self, client_id: str) -> int:
        with self._lock:
            count = 0
            for resource in self._resources.values():
                if resource.owner == client_id:
                    resource.status = "available"
                    resource.owner = None
                    count += 1
            if count:
                self._save_state()
        return count

    def get_status(self) -> dict:
        with self._lock:
            resources = list(self._resources.values())
        available = sum(1 for r in resources if r.status == "available")
        reserved = len(resources) - available
        return {"total": len(resources), "available": available, "reserved": reserved}
