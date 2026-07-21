from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class ChangeType(StrEnum):
    DROP_COLUMN = "drop_column"
    RENAME_COLUMN = "rename_column"
    CHANGE_TYPE = "change_type"


class Criticality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MISSION_CRITICAL = "mission_critical"


class FieldDefinition(BaseModel):
    name: str
    type: str
    nullable: bool = True
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class DataEntity(BaseModel):
    urn: str
    name: str
    entity_type: str
    platform: str
    owner: str | None = None
    domain: str | None = None
    criticality: Criticality = Criticality.MEDIUM
    description: str = ""
    fields: list[FieldDefinition] = Field(default_factory=list)


class LineageEdge(BaseModel):
    source: str
    target: str
    relationship: str = "transforms"
    field_mappings: dict[str, list[str]] = Field(default_factory=dict)


class ChangeRequest(BaseModel):
    entity_urn: str
    field: str
    change_type: ChangeType
    new_name: str | None = None
    new_type: str | None = None
    rationale: str = ""

    @model_validator(mode="after")
    def validate_change_details(self) -> "ChangeRequest":
        if self.change_type == ChangeType.RENAME_COLUMN and not self.new_name:
            raise ValueError("new_name is required for rename_column")
        if self.change_type == ChangeType.CHANGE_TYPE and not self.new_type:
            raise ValueError("new_type is required for change_type")
        return self


class ImpactedEntity(BaseModel):
    urn: str
    name: str
    entity_type: str
    platform: str
    owner: str | None
    criticality: Criticality
    depth: int
    impact_reason: str
    impacted_fields: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    order: int
    title: str
    description: str
    owner: str
    status: Literal["ready", "review", "blocked"] = "ready"


class GeneratedArtifact(BaseModel):
    path: str
    language: str
    purpose: str
    content: str


class AgentTraceStep(BaseModel):
    stage: str
    status: Literal["complete", "warning"]
    detail: str


class WritebackAction(BaseModel):
    action: str
    entity_urn: str
    payload: dict[str, str | list[str] | int | float | bool]


class GraphPayload(BaseModel):
    nodes: list[DataEntity]
    edges: list[LineageEdge]


class AnalysisResult(BaseModel):
    analysis_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request: ChangeRequest
    source: DataEntity
    summary: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    impacted_entities: list[ImpactedEntity]
    graph: GraphPayload
    plan: list[PlanStep]
    artifacts: list[GeneratedArtifact]
    writeback_actions: list[WritebackAction]
    trace: list[AgentTraceStep]


class ApplyRequest(BaseModel):
    approved_by: str = "Demo reviewer"
    note: str = ""


class ApplyResult(BaseModel):
    analysis_id: str
    status: Literal["applied", "simulated"]
    applied_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actions: list[WritebackAction]
    message: str


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex[:10])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    analysis_id: str
    actor: str
    detail: str

