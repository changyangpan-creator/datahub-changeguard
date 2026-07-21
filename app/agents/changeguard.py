from __future__ import annotations

from collections import Counter

from app.graph import MetadataGraph
from app.llm import LLMPlanner
from app.models import (
    AgentTraceStep,
    AnalysisResult,
    ChangeRequest,
    ChangeType,
    Criticality,
    GeneratedArtifact,
    GraphPayload,
    ImpactedEntity,
    PlanStep,
    WritebackAction,
)


CRITICALITY_WEIGHT = {
    Criticality.LOW: 2,
    Criticality.MEDIUM: 5,
    Criticality.HIGH: 10,
    Criticality.MISSION_CRITICAL: 18,
}

CHANGE_WEIGHT = {
    ChangeType.DROP_COLUMN: 22,
    ChangeType.RENAME_COLUMN: 14,
    ChangeType.CHANGE_TYPE: 18,
}


class ChangeGuardAgent:
    def __init__(self, graph: MetadataGraph, llm: LLMPlanner) -> None:
        self.graph = graph
        self.llm = llm

    async def analyze(self, request: ChangeRequest) -> AnalysisResult:
        source = self.graph.get_entity(request.entity_urn)
        source_fields = {field.name: field for field in source.fields}
        if request.field not in source_fields:
            raise ValueError(f"Field `{request.field}` does not exist on {source.name}")

        impacts, nodes, edges = self.graph.downstream_impact(
            request.entity_urn, request.field
        )
        risk_score = self._risk_score(source.criticality, impacts, request.change_type)
        risk_level = self._risk_level(risk_score)
        plan = self._build_plan(request, source.name, impacts, risk_level)
        artifacts = self._build_artifacts(request, source.name, impacts)
        writebacks = self._build_writebacks(request, source.urn, impacts, risk_score)

        evidence_summary = self._evidence_summary(
            request=request,
            source_name=source.name,
            impacts=impacts,
            risk_score=risk_score,
            risk_level=risk_level,
        )
        llm_summary = await self.llm.summarize(
            request=request,
            source=source,
            impacts=impacts,
            risk_score=risk_score,
            deterministic_summary=evidence_summary,
        )

        trace = [
            AgentTraceStep(
                stage="Read DataHub context",
                status="complete",
                detail=(
                    f"Loaded schema, owner, domain and criticality for {source.name}."
                ),
            ),
            AgentTraceStep(
                stage="Traverse field lineage",
                status="complete",
                detail=(
                    f"Followed {len(edges)} lineage edges and found "
                    f"{len(impacts)} downstream assets."
                ),
            ),
            AgentTraceStep(
                stage="Score deployment risk",
                status="complete",
                detail=f"Evidence-based score: {risk_score}/100 ({risk_level}).",
            ),
            AgentTraceStep(
                stage="Generate repair artifacts",
                status="complete",
                detail=f"Produced {len(artifacts)} reviewable files.",
            ),
            AgentTraceStep(
                stage="Prepare DataHub writeback",
                status="complete",
                detail=(
                    "Prepared a decision record, impact tags and ownership follow-ups."
                ),
            ),
        ]

        return AnalysisResult(
            request=request,
            source=source,
            summary=llm_summary,
            risk_score=risk_score,
            risk_level=risk_level,
            impacted_entities=impacts,
            graph=GraphPayload(nodes=nodes, edges=edges),
            plan=plan,
            artifacts=artifacts,
            writeback_actions=writebacks,
            trace=trace,
        )

    def _risk_score(
        self,
        source_criticality: Criticality,
        impacts: list[ImpactedEntity],
        change_type: ChangeType,
    ) -> int:
        score = CHANGE_WEIGHT[change_type] + CRITICALITY_WEIGHT[source_criticality]
        score += min(len(impacts) * 7, 28)
        score += sum(
            min(CRITICALITY_WEIGHT[item.criticality], 12) for item in impacts
        )
        score += sum(6 for item in impacts if not item.owner)
        score += sum(4 for item in impacts if item.depth >= 3)
        return min(score, 100)

    @staticmethod
    def _risk_level(score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 35:
            return "medium"
        return "low"

    @staticmethod
    def _evidence_summary(
        request: ChangeRequest,
        source_name: str,
        impacts: list[ImpactedEntity],
        risk_score: int,
        risk_level: str,
    ) -> str:
        platforms = Counter(item.platform for item in impacts)
        critical = sum(
            item.criticality
            in {Criticality.HIGH, Criticality.MISSION_CRITICAL}
            for item in impacts
        )
        unowned = sum(not item.owner for item in impacts)
        asset_word = "asset" if unowned == 1 else "assets"
        platform_text = ", ".join(
            f"{count} {platform}" for platform, count in platforms.most_common()
        )
        return (
            f"This {request.change_type.value.replace('_', ' ')} on "
            f"`{source_name}.{request.field}` is {risk_level} risk ({risk_score}/100). "
            f"It reaches {len(impacts)} downstream assets across {platform_text or 'no platforms'}, "
            f"including {critical} high-criticality assets and {unowned} {asset_word} without an owner. "
            "Use a compatibility window, deploy downstream repairs first, and record the "
            "decision in DataHub before changing the source."
        )

    @staticmethod
    def _build_plan(
        request: ChangeRequest,
        source_name: str,
        impacts: list[ImpactedEntity],
        risk_level: str,
    ) -> list[PlanStep]:
        owners = sorted({item.owner for item in impacts if item.owner})
        owner_text = ", ".join(owners) if owners else "Data platform lead"
        steps = [
            PlanStep(
                order=1,
                title="Freeze the source contract",
                description=(
                    f"Block the change to `{source_name}.{request.field}` until the "
                    "generated compatibility checks pass."
                ),
                owner="Source owner",
                status="review" if risk_level in {"high", "critical"} else "ready",
            ),
            PlanStep(
                order=2,
                title="Deploy downstream repairs",
                description=(
                    f"Apply the generated patches to {len(impacts)} affected assets, "
                    "starting with the deepest transformations."
                ),
                owner=owner_text,
            ),
            PlanStep(
                order=3,
                title="Run lineage-aware validation",
                description=(
                    "Validate row counts, null rates, schema compatibility and dashboard "
                    "freshness across the impacted graph."
                ),
                owner="Data reliability",
            ),
            PlanStep(
                order=4,
                title="Write the decision back to DataHub",
                description=(
                    "Attach the impact report, approved rollout window and remediation "
                    "links to the source and affected assets."
                ),
                owner="Change approver",
            ),
        ]
        if any(not item.owner for item in impacts):
            steps.insert(
                2,
                PlanStep(
                    order=3,
                    title="Resolve missing ownership",
                    description=(
                        "Assign an accountable owner before rollout; ChangeGuard found "
                        "an operational dependency with no owner."
                    ),
                    owner="Data governance",
                    status="blocked",
                ),
            )
            for index, step in enumerate(steps, start=1):
                step.order = index
        return steps

    def _build_artifacts(
        self,
        request: ChangeRequest,
        source_name: str,
        impacts: list[ImpactedEntity],
    ) -> list[GeneratedArtifact]:
        if request.change_type == ChangeType.RENAME_COLUMN:
            compatibility_expression = (
                f"{request.field} AS {request.new_name},\n    "
                f"{request.field} AS {request.field}  -- temporary compatibility alias"
            )
            migration_note = (
                f"Keep `{request.field}` for one release while consumers move to "
                f"`{request.new_name}`."
            )
        elif request.change_type == ChangeType.CHANGE_TYPE:
            compatibility_expression = (
                f"TRY_CAST({request.field} AS {request.new_type}) AS {request.field}"
            )
            migration_note = (
                f"Quarantine rows that cannot be cast to `{request.new_type}` before rollout."
            )
        else:
            compatibility_expression = (
                f"{request.field}  -- retain during deprecation window"
            )
            migration_note = (
                f"Deprecate `{request.field}` first; remove it only after all consumers migrate."
            )

        downstream_models = [
            item.name for item in impacts if item.entity_type == "dbt model"
        ]
        patch_targets = ", ".join(downstream_models) or "downstream models"

        sql = f"""-- Generated by DataHub ChangeGuard
-- Source: {source_name}
-- {migration_note}

SELECT
    *,
    {compatibility_expression}
FROM {{{{ source('commerce', '{source_name}') }}}}
"""
        schema_test = f"""version: 2

models:
  - name: {downstream_models[0] if downstream_models else 'affected_model'}
    description: "Compatibility guard generated from DataHub field lineage."
    columns:
      - name: {request.new_name or request.field}
        tests:
          - not_null:
              config:
                severity: warn
        meta:
          changeguard:
            source: {source_name}.{request.field}
            patch_targets: "{patch_targets}"
"""
        ci = f"""name: DataHub ChangeGuard

on:
  pull_request:
    paths:
      - "models/**"

jobs:
  lineage-preflight:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run schema compatibility checks
        run: |
          dbt deps
          dbt build --select state:modified+ --fail-fast
      - name: Enforce ChangeGuard approval
        run: |
          test -f changeguard/approved/{source_name}-{request.field}.json
"""
        incident = f"""# Change decision: {source_name}.{request.field}

## Proposed change
- Type: {request.change_type.value}
- Rationale: {request.rationale or 'Not provided'}

## DataHub evidence
- Downstream assets: {len(impacts)}
- Direct owners: {', '.join(sorted({item.owner for item in impacts if item.owner})) or 'None'}
- Unowned assets: {sum(not item.owner for item in impacts)}

## Required rollout
1. Merge generated compatibility patch.
2. Validate every asset in the attached DataHub lineage graph.
3. Obtain owner approval.
4. Write completion evidence back to DataHub.
"""
        return [
            GeneratedArtifact(
                path=f"generated/{source_name}_compatibility.sql",
                language="sql",
                purpose="Backward-compatible source adapter",
                content=sql,
            ),
            GeneratedArtifact(
                path="generated/schema_tests.yml",
                language="yaml",
                purpose="Lineage-aware dbt validation",
                content=schema_test,
            ),
            GeneratedArtifact(
                path=".github/workflows/changeguard.yml",
                language="yaml",
                purpose="Pre-merge deployment gate",
                content=ci,
            ),
            GeneratedArtifact(
                path="changeguard/decision-record.md",
                language="markdown",
                purpose="Auditable change decision",
                content=incident,
            ),
        ]

    @staticmethod
    def _build_writebacks(
        request: ChangeRequest,
        source_urn: str,
        impacts: list[ImpactedEntity],
        risk_score: int,
    ) -> list[WritebackAction]:
        change_id = f"changeguard:{request.field}:{request.change_type.value}"
        actions = [
            WritebackAction(
                action="add_structured_property",
                entity_urn=source_urn,
                payload={
                    "property": "changeguard.last_preflight",
                    "value": change_id,
                },
            ),
            WritebackAction(
                action="add_tag",
                entity_urn=source_urn,
                payload={"tag": f"ChangeRisk:{risk_score}"},
            ),
            WritebackAction(
                action="add_note",
                entity_urn=source_urn,
                payload={
                    "title": "Schema change preflight",
                    "body": (
                        f"{len(impacts)} downstream assets require review before changing "
                        f"`{request.field}`."
                    ),
                },
            ),
        ]
        for item in impacts:
            if not item.owner:
                actions.append(
                    WritebackAction(
                        action="create_ownership_followup",
                        entity_urn=item.urn,
                        payload={
                            "reason": "Impacted by an approved schema change but has no owner"
                        },
                    )
                )
        return actions
