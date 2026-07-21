from __future__ import annotations

from collections import defaultdict, deque
from typing import Protocol

from app.demo_data import DEMO_EDGES, DEMO_ENTITIES
from app.models import DataEntity, ImpactedEntity, LineageEdge


class MetadataGraph(Protocol):
    mode: str

    def list_entities(self) -> list[DataEntity]: ...

    def get_entity(self, urn: str) -> DataEntity: ...

    def downstream_impact(
        self, entity_urn: str, field: str, max_depth: int = 4
    ) -> tuple[list[ImpactedEntity], list[DataEntity], list[LineageEdge]]: ...

    def writeback(self, actions: list[dict]) -> list[dict]: ...


class DemoMetadataGraph:
    mode = "demo"

    def __init__(self) -> None:
        self._entities = {entity.urn: entity for entity in DEMO_ENTITIES}
        self._edges = list(DEMO_EDGES)
        self._writebacks: list[dict] = []

    def list_entities(self) -> list[DataEntity]:
        return list(self._entities.values())

    def get_entity(self, urn: str) -> DataEntity:
        if urn not in self._entities:
            raise KeyError(f"Unknown entity: {urn}")
        return self._entities[urn]

    def downstream_impact(
        self, entity_urn: str, field: str, max_depth: int = 4
    ) -> tuple[list[ImpactedEntity], list[DataEntity], list[LineageEdge]]:
        adjacency: dict[str, list[LineageEdge]] = defaultdict(list)
        for edge in self._edges:
            adjacency[edge.source].append(edge)

        queue = deque([(entity_urn, field, 0)])
        visited: set[tuple[str, str]] = {(entity_urn, field)}
        impacted: dict[str, ImpactedEntity] = {}
        selected_edges: list[LineageEdge] = []

        while queue:
            current_urn, current_field, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in adjacency.get(current_urn, []):
                mapped_fields = edge.field_mappings.get(current_field)
                if mapped_fields is None:
                    continue

                selected_edges.append(edge)
                target = self._entities[edge.target]
                target_fields = mapped_fields or [current_field]
                reason = (
                    f"Consumes `{current_field}` from {self._entities[current_urn].name}"
                    if mapped_fields
                    else f"Operationally depends on {self._entities[current_urn].name}"
                )

                existing = impacted.get(target.urn)
                if existing:
                    existing.impacted_fields = sorted(
                        set(existing.impacted_fields).union(target_fields)
                    )
                    existing.depth = min(existing.depth, depth + 1)
                else:
                    impacted[target.urn] = ImpactedEntity(
                        urn=target.urn,
                        name=target.name,
                        entity_type=target.entity_type,
                        platform=target.platform,
                        owner=target.owner,
                        criticality=target.criticality,
                        depth=depth + 1,
                        impact_reason=reason,
                        impacted_fields=target_fields,
                    )

                for target_field in target_fields:
                    key = (target.urn, target_field)
                    if key not in visited:
                        visited.add(key)
                        queue.append((target.urn, target_field, depth + 1))

        graph_urns = {entity_urn, *impacted.keys()}
        nodes = [self._entities[urn] for urn in graph_urns]
        edge_keys: set[tuple[str, str, str]] = set()
        edges: list[LineageEdge] = []
        for edge in selected_edges:
            key = (edge.source, edge.target, edge.relationship)
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append(edge)

        impacts = sorted(impacted.values(), key=lambda item: (item.depth, item.name))
        return impacts, nodes, edges

    def writeback(self, actions: list[dict]) -> list[dict]:
        self._writebacks.extend(actions)
        return actions

    @property
    def writebacks(self) -> list[dict]:
        return list(self._writebacks)

