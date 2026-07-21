from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.changeguard import ChangeGuardAgent
from app.integrations.datahub import build_metadata_graph
from app.llm import LLMPlanner
from app.models import (
    AnalysisResult,
    ApplyRequest,
    ApplyResult,
    AuditEvent,
    ChangeRequest,
    DataEntity,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="DataHub ChangeGuard",
    description="Schema change preflight, repair generation and DataHub writeback.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

graph = build_metadata_graph()
llm = LLMPlanner()
agent = ChangeGuardAgent(graph=graph, llm=llm)
analyses: dict[str, AnalysisResult] = {}
audit_log: list[AuditEvent] = []


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status() -> dict:
    return {
        "name": "DataHub ChangeGuard",
        "mode": graph.mode,
        "mcp_enabled": getattr(graph, "mcp", None) is not None,
        "llm_enabled": llm.enabled,
        "analysis_count": len(analyses),
        "writeback_count": len(audit_log),
    }


@app.get("/api/entities", response_model=list[DataEntity])
async def list_entities() -> list[DataEntity]:
    return graph.list_entities()


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_change(request: ChangeRequest) -> AnalysisResult:
    try:
        result = await agent.analyze(request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    analyses[result.analysis_id] = result
    audit_log.append(
        AuditEvent(
            event_type="analysis_created",
            analysis_id=result.analysis_id,
            actor="ChangeGuard agent",
            detail=(
                f"Analyzed {request.change_type.value} on "
                f"{result.source.name}.{request.field}."
            ),
        )
    )
    return result


@app.get("/api/analyses/{analysis_id}", response_model=AnalysisResult)
async def get_analysis(analysis_id: str) -> AnalysisResult:
    if analysis_id not in analyses:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analyses[analysis_id]


@app.post("/api/analyses/{analysis_id}/apply", response_model=ApplyResult)
async def apply_writeback(analysis_id: str, request: ApplyRequest) -> ApplyResult:
    result = analyses.get(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")

    serialized_actions = [action.model_dump(mode="json") for action in result.writeback_actions]
    graph.writeback(serialized_actions)
    status_value = "simulated" if graph.mode == "demo" else "applied"
    audit_log.append(
        AuditEvent(
            event_type="writeback_applied",
            analysis_id=analysis_id,
            actor=request.approved_by,
            detail=request.note or "Approved the ChangeGuard DataHub writeback plan.",
        )
    )
    return ApplyResult(
        analysis_id=analysis_id,
        status=status_value,
        actions=result.writeback_actions,
        message=(
            "Demo writeback recorded in the audit trail."
            if graph.mode == "demo"
            else "Change decision written to DataHub."
        ),
    )


@app.get("/api/audit", response_model=list[AuditEvent])
async def get_audit_log() -> list[AuditEvent]:
    return list(reversed(audit_log))
