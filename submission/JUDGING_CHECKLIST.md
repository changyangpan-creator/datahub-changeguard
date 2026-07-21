# Submission Checklist

## Pass/fail requirements

- [x] New working software project created during the submission period.
- [x] Uses the DataHub open-source platform.
- [x] Incorporates the DataHub MCP Server.
- [x] Apache 2.0 `LICENSE` included.
- [x] Source code and complete local setup instructions included.
- [x] Sample generated artifacts included in `examples/generated`.
- [ ] Public open-source repository URL.
- [ ] Apache 2.0 license detected in the repository About section.
- [ ] Public working demo URL, or clear local testing path accepted by the submission form.
- [ ] Public video URL on YouTube, Vimeo, or Youku.
- [ ] Video duration under 3 minutes.
- [ ] Devpost submission fields completed and saved.
- [ ] Final submission entered before August 10, 2026 at 5:00 PM EDT.

## Judging criteria evidence

### Use of DataHub

- MCP calls: `get_entities`, `list_schema_fields`, `get_lineage`.
- Context: schema, field lineage, ownership, domain, criticality, dashboards, pipelines,
  and ML assets.
- Writeback: incidents and institutional-memory links.

### Technical execution

- Deterministic graph traversal and risk engine.
- Typed FastAPI API.
- Credential-free demo mode.
- Real DataHub mode.
- Automated tests.
- Browser-tested end-to-end analysis and writeback flow.

### Originality

- Pre-deployment change control rather than catalog Q&A.
- Generates code, tests, CI policy, and decision records.
- Human approval boundary before governed writeback.

### Real-world usefulness

- Prevents analytics and ML breakage from schema changes.
- Finds unowned dependencies.
- Routes repair steps to accountable teams.

### Submission quality

- README with architecture and setup.
- Less-than-3-minute script.
- Sample outputs.
- Devpost-ready description.

## Final manual checks

- [ ] Replace every placeholder URL.
- [ ] Test the public repository from a signed-out browser.
- [ ] Test the public demo from a signed-out browser.
- [ ] Confirm no secrets exist in git history.
- [ ] Confirm screenshots and video show the corrected red/amber/green graph legend.
- [ ] Submit actionable DataHub SDK/documentation feedback for the bonus category.

