from __future__ import annotations

import os
import json
import re
from itertools import count
from typing import Any
from urllib.parse import quote

import httpx

from app.graph import DemoMetadataGraph, MetadataGraph
from app.models import Criticality, DataEntity, FieldDefinition, ImpactedEntity, LineageEdge


class DataHubMCPContext:
    """Small streamable-HTTP MCP client for DataHub's Agent Context tools."""

    def __init__(
        self,
        url: str,
        token: str,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.url = url
        self.client = httpx.Client(headers=headers, timeout=timeout, transport=transport)
        self.session_id: str | None = None
        self._request_ids = count(1)
        self._tools: dict[str, dict[str, Any]] | None = None

    def collect_change_context(
        self, entity_urn: str, field: str, max_depth: int
    ) -> dict[str, Any]:
        self._ensure_initialized()
        context = {
            "entity": self.call_tool(
                "get_entities",
                {"urns": [entity_urn], "urn": entity_urn},
            ),
            "schema": self.call_tool(
                "list_schema_fields",
                {
                    "urn": entity_urn,
                    "entity_urn": entity_urn,
                    "query": field,
                    "keyword": field,
                },
            ),
            "lineage": self.call_tool(
                "get_lineage",
                {
                    "urn": entity_urn,
                    "entity_urn": entity_urn,
                    "direction": "downstream",
                    "max_hops": max_depth,
                    "max_depth": max_depth,
                },
            ),
        }
        return context

    def call_tool(self, name: str, candidates: dict[str, Any]) -> dict[str, Any]:
        self._ensure_initialized()
        if not self._tools or name not in self._tools:
            raise RuntimeError(f"DataHub MCP tool is unavailable: {name}")
        schema = self._tools[name].get("inputSchema") or {}
        arguments = self._arguments_for_schema(schema, candidates)
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        if result.get("isError"):
            raise RuntimeError(self._tool_text(result) or f"DataHub MCP tool failed: {name}")
        return {
            "tool": name,
            "arguments": arguments,
            "content": self._tool_content(result),
        }

    def _ensure_initialized(self) -> None:
        if self._tools is not None:
            return
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "DataHub ChangeGuard", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized")
        tools = self._request("tools/list", {}).get("tools") or []
        self._tools = {tool["name"]: tool for tool in tools}

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = next(self._request_ids)
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        response = self.client.post(self.url, headers=self._session_headers(), json=payload)
        response.raise_for_status()
        if response.headers.get("mcp-session-id"):
            self.session_id = response.headers["mcp-session-id"]
        message = self._decode_message(response)
        if message.get("error"):
            raise RuntimeError(message["error"].get("message", "DataHub MCP request failed"))
        return message.get("result") or {}

    def _notify(self, method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        response = self.client.post(self.url, headers=self._session_headers(), json=payload)
        response.raise_for_status()

    def _session_headers(self) -> dict[str, str]:
        return {"Mcp-Session-Id": self.session_id} if self.session_id else {}

    @staticmethod
    def _decode_message(response: httpx.Response) -> dict[str, Any]:
        if "text/event-stream" not in response.headers.get("content-type", ""):
            return response.json()
        messages = []
        for line in response.text.splitlines():
            if line.startswith("data:"):
                messages.append(json.loads(line.removeprefix("data:").strip()))
        if not messages:
            raise RuntimeError("DataHub MCP returned an empty event stream")
        return messages[-1]

    @staticmethod
    def _arguments_for_schema(
        schema: dict[str, Any], candidates: dict[str, Any]
    ) -> dict[str, Any]:
        properties = schema.get("properties") or {}
        arguments = {
            name: candidates[name]
            for name in properties
            if name in candidates and candidates[name] is not None
        }
        missing = [
            name
            for name in schema.get("required") or []
            if name not in arguments
        ]
        if missing:
            raise RuntimeError(
                f"Unsupported DataHub MCP tool schema; missing arguments: {', '.join(missing)}"
            )
        return arguments

    @classmethod
    def _tool_content(cls, result: dict[str, Any]) -> list[Any]:
        content = []
        for item in result.get("content") or []:
            text = item.get("text") if isinstance(item, dict) else None
            if text:
                try:
                    content.append(json.loads(text))
                except json.JSONDecodeError:
                    content.append(text)
            else:
                content.append(item)
        return content

    @staticmethod
    def _tool_text(result: dict[str, Any]) -> str:
        return " ".join(
            item.get("text", "")
            for item in result.get("content") or []
            if isinstance(item, dict)
        )


class DataHubMetadataGraph:
    mode = "datahub"

    def __init__(
        self,
        base_url: str,
        token: str,
        public_url: str | None = None,
        mcp_url: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.public_url = (public_url or base_url).rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "X-RestLi-Protocol-Version": "2.0.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(headers=headers, timeout=timeout)
        self.mcp = DataHubMCPContext(
            url=mcp_url or f"{self.base_url}/mcp",
            token=token,
            timeout=timeout,
        )
        self.last_mcp_context: dict[str, Any] | None = None

    def list_entities(self) -> list[DataEntity]:
        query = """
        query ChangeGuardDatasets($input: ScrollAcrossEntitiesInput!) {
          scrollAcrossEntities(input: $input) {
            searchResults {
              entity {
                urn
                type
                ... on Dataset {
                  name
                  platform { name }
                }
              }
            }
          }
        }
        """
        data = self._graphql(
            query,
            {"input": {"types": ["DATASET"], "query": "*", "count": 50}},
        )
        results = data["scrollAcrossEntities"]["searchResults"]
        entities = []
        for result in results:
            entity = result["entity"]
            entities.append(
                DataEntity(
                    urn=entity["urn"],
                    name=entity.get("name") or self._name_from_urn(entity["urn"]),
                    entity_type="dataset",
                    platform=(entity.get("platform") or {}).get("name") or "DataHub",
                )
            )
        return entities

    def get_entity(self, urn: str) -> DataEntity:
        response = self.client.get(f"{self.base_url}/entitiesV2/{quote(urn, safe='')}")
        response.raise_for_status()
        return self._parse_entity(urn, response.json())

    def downstream_impact(
        self, entity_urn: str, field: str, max_depth: int = 4
    ) -> tuple[list[ImpactedEntity], list[DataEntity], list[LineageEdge]]:
        self.last_mcp_context = self.mcp.collect_change_context(
            entity_urn=entity_urn,
            field=field,
            max_depth=max_depth,
        )
        degrees = [str(depth) for depth in range(1, max_depth)]
        degrees.append(f"{max_depth}+")
        query = """
        query ChangeGuardLineage($input: ScrollAcrossLineageInput!) {
          scrollAcrossLineage(input: $input) {
            searchResults {
              degree
              entity { urn type }
            }
          }
        }
        """
        data = self._graphql(
            query,
            {
                "input": {
                    "urn": entity_urn,
                    "direction": "DOWNSTREAM",
                    "query": "*",
                    "count": 100,
                    "orFilters": [
                        {
                            "and": [
                                {
                                    "field": "degree",
                                    "condition": "EQUAL",
                                    "negated": False,
                                    "values": degrees,
                                }
                            ]
                        }
                    ],
                }
            },
        )

        source = self.get_entity(entity_urn)
        nodes = [source]
        impacts: list[ImpactedEntity] = []
        edges: list[LineageEdge] = []
        for result in data["scrollAcrossLineage"]["searchResults"]:
            target_urn = result["entity"]["urn"]
            target = self.get_entity(target_urn)
            depth = self._parse_degree(result.get("degree"))
            nodes.append(target)
            impacts.append(
                ImpactedEntity(
                    urn=target.urn,
                    name=target.name,
                    entity_type=target.entity_type,
                    platform=target.platform,
                    owner=target.owner,
                    criticality=target.criticality,
                    depth=depth,
                    impact_reason=(
                        f"DataHub MCP reports a downstream lineage dependency at depth {depth}"
                    ),
                    impacted_fields=[field],
                )
            )
            edges.append(
                LineageEdge(
                    source=entity_urn,
                    target=target.urn,
                    relationship=f"downstream depth {depth}",
                    field_mappings={field: [field]},
                )
            )
        impacts.sort(key=lambda item: (item.depth, item.name))
        return impacts, nodes, edges

    def writeback(self, actions: list[dict]) -> list[dict]:
        applied = []
        for action in actions:
            entity_urn = action["entity_urn"]
            action_name = action["action"]
            payload = action.get("payload", {})
            label = f"ChangeGuard: {action_name.replace('_', ' ')}"

            if action_name in {"add_note", "create_ownership_followup"}:
                title = str(payload.get("title") or "ChangeGuard ownership follow-up")
                description = str(payload.get("body") or payload.get("reason") or label)
                incident_urn = self._graphql(
                    """
                    mutation ChangeGuardIncident($input: RaiseIncidentInput!) {
                      raiseIncident(input: $input)
                    }
                    """,
                    {
                        "input": {
                            "resourceUrn": entity_urn,
                            "type": "CUSTOM",
                            "customType": "Schema Change Preflight",
                            "title": title,
                            "description": description,
                        }
                    },
                )["raiseIncident"]
                applied.append(
                    {
                        **action,
                        "datahub_operation": "raiseIncident",
                        "result": incident_urn,
                    }
                )
                continue

            result = self._graphql(
                """
                mutation ChangeGuardLink($input: UpsertLinkInput!) {
                  upsertLink(input: $input)
                }
                """,
                {
                    "input": {
                        "resourceUrn": entity_urn,
                        "linkUrl": self.public_url,
                        "label": label,
                    }
                },
            )["upsertLink"]
            applied.append(
                {
                    **action,
                    "datahub_operation": "upsertLink",
                    "result": result,
                }
            )
        return applied

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/api/graphql",
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            message = "; ".join(error.get("message", "GraphQL error") for error in payload["errors"])
            raise RuntimeError(message)
        return payload["data"]

    @classmethod
    def _parse_entity(cls, urn: str, payload: dict[str, Any]) -> DataEntity:
        aspects = cls._aspect_values(payload)
        dataset_key = aspects.get("datasetKey", {})
        properties = cls._first_aspect(
            aspects,
            "datasetProperties",
            "dashboardInfo",
            "chartInfo",
            "dataJobInfo",
            "dataFlowInfo",
            "mlModelProperties",
        )
        schema = aspects.get("schemaMetadata", {})
        ownership = aspects.get("ownership", {})
        domains = aspects.get("domains", {})
        criticality = aspects.get("dataHubPolicyInfo", {}).get("criticality")

        platform_urn = dataset_key.get("platform", "")
        platform = cls._name_from_urn(platform_urn) if platform_urn else "DataHub"
        name = (
            properties.get("name")
            or properties.get("title")
            or dataset_key.get("name")
            or cls._name_from_urn(urn)
        )
        owners = ownership.get("owners") or []
        owner = None
        if owners:
            owner = cls._name_from_urn(owners[0].get("owner", ""))
        domain_urns = domains.get("domains") or []
        first_domain = domain_urns[0] if domain_urns else ""
        if isinstance(first_domain, dict):
            first_domain = first_domain.get("urn", "")
        domain = cls._name_from_urn(first_domain) if first_domain else None

        fields = []
        for item in schema.get("fields") or []:
            native_type = item.get("nativeDataType")
            type_payload = item.get("type", {}).get("type", {})
            type_name = native_type or next(iter(type_payload), "UNKNOWN")
            fields.append(
                FieldDefinition(
                    name=item.get("fieldPath") or item.get("fieldPathV2") or "unknown",
                    type=type_name,
                    nullable=item.get("nullable", True),
                    description=item.get("description", ""),
                )
            )

        entity_type = cls._entity_type_from_urn(urn, platform)
        return DataEntity(
            urn=urn,
            name=name,
            entity_type=entity_type,
            platform=platform,
            owner=owner,
            domain=domain,
            criticality=cls._criticality(criticality),
            description=properties.get("description", ""),
            fields=fields,
        )

    @staticmethod
    def _aspect_values(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw = payload.get("value", payload)
        aspects: dict[str, dict[str, Any]] = {}
        for qualified_name, wrapper in raw.items():
            short_name = qualified_name.rsplit(".", 1)[-1]
            short_name = short_name[:1].lower() + short_name[1:]
            value = wrapper.get("value", wrapper) if isinstance(wrapper, dict) else {}
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    value = {}
            if isinstance(value, dict):
                aspects[short_name] = value
        return aspects

    @staticmethod
    def _first_aspect(
        aspects: dict[str, dict[str, Any]], *names: str
    ) -> dict[str, Any]:
        for name in names:
            if name in aspects:
                return aspects[name]
        return {}

    @staticmethod
    def _parse_degree(value: Any) -> int:
        match = re.search(r"\d+", str(value or "1"))
        return int(match.group()) if match else 1

    @staticmethod
    def _name_from_urn(urn: str) -> str:
        if not urn:
            return ""
        value = urn.rsplit(":", 1)[-1].strip("()")
        return value.split(",")[-2] if "," in value else value

    @staticmethod
    def _entity_type_from_urn(urn: str, platform: str) -> str:
        if ":dashboard:" in urn:
            return "dashboard"
        if ":chart:" in urn:
            return "chart"
        if ":dataJob:" in urn:
            return "pipeline job"
        if ":dataFlow:" in urn:
            return "pipeline"
        if ":mlModel:" in urn:
            return "ML model"
        if platform.lower() == "dbt":
            return "dbt model"
        return "dataset"

    @staticmethod
    def _criticality(value: Any) -> Criticality:
        normalized = str(value or "").lower().replace("-", "_")
        aliases = {
            "low": Criticality.LOW,
            "medium": Criticality.MEDIUM,
            "high": Criticality.HIGH,
            "mission_critical": Criticality.MISSION_CRITICAL,
        }
        return aliases.get(normalized, Criticality.MEDIUM)


def build_metadata_graph() -> MetadataGraph:
    mode = os.getenv("CHANGEGUARD_MODE", "demo").lower()
    if mode == "demo":
        return DemoMetadataGraph()
    if mode == "datahub":
        base_url = os.getenv("DATAHUB_GMS_URL", "").strip()
        if not base_url:
            raise RuntimeError("DATAHUB_GMS_URL is required in datahub mode")
        return DataHubMetadataGraph(
            base_url=base_url,
            token=os.getenv("DATAHUB_TOKEN", ""),
            public_url=os.getenv("CHANGEGUARD_PUBLIC_URL"),
            mcp_url=os.getenv("DATAHUB_MCP_URL"),
        )
    raise RuntimeError("CHANGEGUARD_MODE must be either 'demo' or 'datahub'")
