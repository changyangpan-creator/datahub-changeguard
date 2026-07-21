import json

import httpx

from app.integrations.datahub import DataHubMCPContext, DataHubMetadataGraph
from app.models import Criticality


URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,commerce.orders,PROD)"


def entity_payload() -> dict:
    return {
        "value": {
            "com.linkedin.pegasus2avro.dataset.DatasetKey": {
                "value": {
                    "platform": "urn:li:dataPlatform:snowflake",
                    "name": "commerce.orders",
                }
            },
            "com.linkedin.pegasus2avro.dataset.DatasetProperties": {
                "value": json.dumps(
                    {
                        "name": "orders",
                        "description": "Commerce orders.",
                    }
                )
            },
            "com.linkedin.pegasus2avro.schema.SchemaMetadata": {
                "value": {
                    "fields": [
                        {
                            "fieldPath": "total_amount",
                            "nativeDataType": "DECIMAL(12,2)",
                            "nullable": False,
                            "description": "Gross order amount.",
                        }
                    ]
                }
            },
            "com.linkedin.pegasus2avro.common.Ownership": {
                "value": {
                    "owners": [{"owner": "urn:li:corpGroup:commerce-data"}]
                }
            },
            "com.linkedin.pegasus2avro.domain.Domains": {
                "value": {"domains": ["urn:li:domain:commerce"]}
            },
        }
    }


def test_parse_entities_v2_payload() -> None:
    entity = DataHubMetadataGraph._parse_entity(URN, entity_payload())

    assert entity.name == "orders"
    assert entity.platform == "snowflake"
    assert entity.owner == "commerce-data"
    assert entity.domain == "commerce"
    assert entity.criticality == Criticality.MEDIUM
    assert entity.fields[0].name == "total_amount"
    assert entity.fields[0].nullable is False


def test_writeback_maps_notes_to_incidents_and_metadata_to_links() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        operation = body["query"]
        if "raiseIncident" in operation:
            return httpx.Response(200, json={"data": {"raiseIncident": "urn:li:incident:1"}})
        return httpx.Response(200, json={"data": {"upsertLink": True}})

    graph = DataHubMetadataGraph("http://datahub.test", "token")
    graph.client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer token"},
    )
    result = graph.writeback(
        [
            {
                "action": "add_note",
                "entity_urn": URN,
                "payload": {"title": "Preflight", "body": "Review required."},
            },
            {
                "action": "add_tag",
                "entity_urn": URN,
                "payload": {"tag": "ChangeRisk:88"},
            },
        ]
    )

    assert [item["datahub_operation"] for item in result] == [
        "raiseIncident",
        "upsertLink",
    ]
    assert len(requests) == 2
    assert requests[0].headers["authorization"] == "Bearer token"


def test_lineage_degree_parser_handles_plus_bucket() -> None:
    assert DataHubMetadataGraph._parse_degree("3+") == 3
    assert DataHubMetadataGraph._parse_degree(2) == 2


def test_mcp_context_discovers_and_calls_required_tools() -> None:
    called_tools: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body["method"]
        if method == "initialize":
            return httpx.Response(
                200,
                headers={"Mcp-Session-Id": "session-1"},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        if method == "notifications/initialized":
            assert request.headers["mcp-session-id"] == "session-1"
            return httpx.Response(202)
        if method == "tools/list":
            tools = [
                {
                    "name": "get_entities",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"urns": {"type": "array"}},
                        "required": ["urns"],
                    },
                },
                {
                    "name": "list_schema_fields",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "urn": {"type": "string"},
                            "query": {"type": "string"},
                        },
                        "required": ["urn"],
                    },
                },
                {
                    "name": "get_lineage",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "urn": {"type": "string"},
                            "direction": {"type": "string"},
                            "max_hops": {"type": "integer"},
                        },
                        "required": ["urn"],
                    },
                },
            ]
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": body["id"], "result": {"tools": tools}},
            )
        called_tools.append(body["params"]["name"])
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"ok": body["params"]["name"]}),
                        }
                    ]
                },
            },
        )

    context = DataHubMCPContext(
        "http://datahub.test/mcp",
        "token",
        transport=httpx.MockTransport(handler),
    )
    result = context.collect_change_context(URN, "total_amount", 4)

    assert called_tools == ["get_entities", "list_schema_fields", "get_lineage"]
    assert result["lineage"]["arguments"]["direction"] == "downstream"
    assert result["lineage"]["content"] == [{"ok": "get_lineage"}]
