from typing import List, Literal, Union
from pydantic import BaseModel, Field


class Identity(BaseModel):
    name: str
    version: str
    author: str
    description: str


class PermissionInference(BaseModel):
    type: Literal["inference:run"]
    model: str


class PermissionNetwork(BaseModel):
    type: Literal["network:egress"]
    target: str


Permission = Union[PermissionInference, PermissionNetwork]


class ResourceLimits(BaseModel):
    cpu: str
    memory: str
    execution_timeout: str = Field(..., alias="executionTimeout")


class SecurityContext(BaseModel):
    trust_tier: Literal["community", "partner", "core"] = Field(..., alias="trustTier")
    permissions: List[Permission]
    resource_limits: ResourceLimits = Field(..., alias="resourceLimits")


class Build(BaseModel):
    language: str
    version: str
    entrypoint: str


class PluginManifest(BaseModel):
    schema_version: str = Field(..., alias="schemaVersion")
    identity: Identity
    security_context: SecurityContext = Field(..., alias="securityContext")
    build: Build
