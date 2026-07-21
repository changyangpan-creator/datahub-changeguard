# DataHub ChangeGuard

## Tagline

Catch schema breakage before merge and generate the files needed to fix it.

## Category

- Agents That Do Real Work
- Metadata-Aware Code Generation & Development
- Production ML Agents

## Inspiration

Dropping one column can break a dbt model, an executive dashboard, an ML feature, and the
Airflow job that refreshes them. The engineer proposing the change then has to trace the
dependencies, find four different owners, write compatibility code, and record the
decision.

DataHub already stores most of that evidence. ChangeGuard uses it before the source schema
changes.

## What it does

The engineer selects a DataHub asset, a field, and a proposed change. ChangeGuard reads
the schema and downstream graph, then returns a release decision with the evidence behind
it.

For the default demo, dropping `raw_orders.total_amount` reaches six assets:

- two dbt models;
- an executive Looker dashboard;
- a Snowflake feature table and a production churn model;
- an Airflow job with no owner.

ChangeGuard scores the change at 100/100 and blocks the release. It generates a
compatibility SQL patch, dbt tests, a GitHub Actions check, and a Markdown decision
record. The repair plan names the responsible teams and adds an ownership task for the
unowned Airflow job.

After a reviewer approves the plan, ChangeGuard writes an incident and supporting links
back to DataHub.

## How we built it

The API uses FastAPI and Pydantic. A small streamable-HTTP MCP client connects to the
DataHub MCP Server and calls `get_entities`, `list_schema_fields`, and `get_lineage`.

The real-instance adapter also uses:

- `entitiesV2` for schema, ownership, domains, and other entity aspects;
- `scrollAcrossLineage` for structured downstream traversal;
- `raiseIncident` and `upsertLink` for approved writeback.

The demo graph includes explicit field mappings, so the agent can follow
`total_amount -> gross_revenue -> lifetime_value -> churn_probability` instead of marking
every downstream field as affected.

Risk scoring and artifact generation use fixed rules. The optional OpenAI Responses API
rewrites the short summary, but it does not change the score, graph, plan, or generated
files.

Cytoscape renders the lineage graph. The interface keeps the request, graph, release
decision, generated files, and rollout plan on one screen.

## How DataHub is used

ChangeGuard needs several DataHub aspects at the same time:

- schema fields identify the proposed change;
- lineage identifies direct and multi-hop consumers;
- criticality changes the release score;
- ownership determines who reviews each repair;
- dashboard, pipeline, and ML metadata show where the breakage reaches.

The agent then writes the approved decision back to the affected asset. Without DataHub,
the tool would have a column name but no reliable dependency graph, owners, or place to
store the result.

## What is different

ChangeGuard runs before deployment and produces files that can enter a pull request.
A catalog search can show that a dashboard depends on a table. ChangeGuard uses the same
metadata to decide whether the change should ship, drafts the compatibility work, and
records the approval.

The human approval step stays visible. The agent can prepare an incident and links, but a
reviewer decides whether to write them to DataHub.

## Challenges

Field lineage was the first difficult part. Entity-level lineage alone produces too many
false positives, so the demo graph carries field mappings through each hop. The real
adapter collects MCP context and keeps the GraphQL result structured for scoring and
display.

The second issue was judge access. A DataHub instance and API credentials should not be
required to understand the project, so the repository includes a fixed commerce graph and
sample outputs. Real mode uses the same API and decision model.

Writeback also needed a review boundary. The first version treated generated actions as
if they could be applied at once. The current flow separates analysis from approval and
records the reviewer in the audit log.

## Current result

- The default change reaches six downstream assets and four owner groups.
- ChangeGuard generates four reviewable files and a five-step repair plan.
- The repository includes demo and real DataHub modes.
- Eight automated tests cover traversal, scoring, artifact generation, MCP negotiation,
  entity parsing, and writeback mapping.
- The interface has been checked at standard desktop width and 1024px without horizontal
  overflow.

## What we learned

Lineage alone does not produce a release plan. Ownership changes who must review the
change, and criticality changes how cautiously the team should roll it out. Missing
ownership is also a release risk, not a catalog cleanup task for later.

Generated prose was the least useful output. SQL, tests, a CI check, and a named owner give
the reviewer something they can act on.

## Next work

- Open a pull request with the generated repair files.
- Read fine-grained field mappings from a connected DataHub instance.
- Close the DataHub incident after every downstream owner signs off.
- Package the preflight as a reusable DataHub Skill and CI command.

## Built during the hackathon

This repository was created during the July 6 to August 10, 2026 submission period. Its
dependencies are listed in `pyproject.toml`, and the code is licensed under Apache 2.0.

## Testing instructions

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn app.main:app --port 8765
```

Open `http://127.0.0.1:8765`. Keep the default `raw_orders.total_amount` drop scenario and
click **Run preflight**. Review the graph and generated files, then click
**Approve DataHub writeback**.

