from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class Location(BaseModel):
    model_config = ConfigDict(frozen=False)
    node: str
    user: str
    ports: List[int] = []


class Resource(BaseModel):
    model_config = ConfigDict(frozen=False)
    resource_class: str
    name: str
    enumerator: str
    location: Location
    status: str = "available"
    owner: Optional[str] = None


class ResourceIdentifier(BaseModel):
    resource_class: str
    name: str
    enumerator: str


class ReservationRequest(BaseModel):
    client_id: str
    resources: List[ResourceIdentifier]


class ReleaseRequest(BaseModel):
    client_id: str
    resources: List[ResourceIdentifier]


class ServerStatus(BaseModel):
    total: int
    available: int
    reserved: int
