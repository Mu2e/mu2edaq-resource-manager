from pydantic import BaseModel, ConfigDict, Field
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
    # client_id is accepted for backward compatibility but ignored: the owner
    # is the authenticated principal. See server auth.
    client_id: Optional[str] = None
    resources: List[ResourceIdentifier] = Field(..., min_length=1)


class ReleaseRequest(BaseModel):
    client_id: Optional[str] = None
    resources: List[ResourceIdentifier] = Field(..., min_length=1)


class ServerStatus(BaseModel):
    total: int
    available: int
    reserved: int
