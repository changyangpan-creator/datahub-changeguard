import asyncio

import pytest

from app.agents.changeguard import ChangeGuardAgent
from app.graph import DemoMetadataGraph
from app.llm import LLMPlanner
from app.models import ChangeRequest, ChangeType


@pytest.fixture
def graph() -> DemoMetadataGraph:
    return DemoMetadataGraph()


@pytest.fixture
def agent(graph: DemoMetadataGraph) -> ChangeGuardAgent:
    planner = LLMPlanner()
    planner.client = None
    return ChangeGuardAgent(graph=graph, llm=planner)


def raw_orders_urn(graph: DemoMetadataGraph) -> str:
    return next(entity.urn for entity in graph.list_entities() if entity.name == "raw_orders")


def test_field_lineage_reaches_dashboard_and_model(graph: DemoMetadataGraph) -> None:
    impacts, _, _ = graph.downstream_impact(raw_orders_urn(graph), "total_amount")
    names = {item.name for item in impacts}

    assert "Executive Revenue Dashboard" in names
    assert "churn_prediction_v3" in names
    assert any(item.depth >= 3 for item in impacts)


def test_analysis_generates_reviewable_artifacts(
    agent: ChangeGuardAgent, graph: DemoMetadataGraph
) -> None:
    result = asyncio.run(
        agent.analyze(
            ChangeRequest(
                entity_urn=raw_orders_urn(graph),
                field="total_amount",
                change_type=ChangeType.DROP_COLUMN,
                rationale="Retire a legacy field.",
            )
        )
    )

    assert result.risk_level in {"high", "critical"}
    assert result.risk_score >= 60
    assert len(result.artifacts) == 4
    assert any(artifact.language == "sql" for artifact in result.artifacts)
    assert any("DataHub" in step.title for step in result.plan)
    assert result.writeback_actions


def test_missing_field_is_rejected(
    agent: ChangeGuardAgent, graph: DemoMetadataGraph
) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        asyncio.run(
            agent.analyze(
                ChangeRequest(
                    entity_urn=raw_orders_urn(graph),
                    field="not_a_real_field",
                    change_type=ChangeType.DROP_COLUMN,
                )
            )
        )


def test_rename_requires_new_name(graph: DemoMetadataGraph) -> None:
    with pytest.raises(ValueError, match="new_name"):
        ChangeRequest(
            entity_urn=raw_orders_urn(graph),
            field="total_amount",
            change_type=ChangeType.RENAME_COLUMN,
        )
