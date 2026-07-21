const state = {
  entities: [],
  analysis: null,
  selectedArtifact: 0,
  graph: null,
};

const $ = (selector) => document.querySelector(selector);

const els = {
  form: $("#change-form"),
  entity: $("#entity-select"),
  field: $("#field-select"),
  changeType: $("#change-type"),
  newNameGroup: $("#new-name-group"),
  newTypeGroup: $("#new-type-group"),
  newName: $("#new-name"),
  newType: $("#new-type"),
  rationale: $("#rationale"),
  analyze: $("#analyze-button"),
  sourceContext: $("#source-context"),
  graph: $("#lineage-graph"),
  graphTitle: $("#graph-title"),
  mode: $("#mode-label"),
  traceList: $("#trace-list"),
  traceCount: $("#trace-count"),
  score: $("#risk-score"),
  decision: $("#decision-banner"),
  summary: $("#summary"),
  assetCount: $("#asset-count"),
  ownerCount: $("#owner-count"),
  unownedCount: $("#unowned-count"),
  impactCount: $("#impact-count"),
  impactList: $("#impact-list"),
  writeback: $("#writeback-button"),
  artifactTabs: $("#artifact-tabs"),
  artifactCode: $("#artifact-code"),
  copy: $("#copy-button"),
  download: $("#download-button"),
  planList: $("#plan-list"),
  toast: $("#toast"),
  refresh: $("#refresh-button"),
};

function icon(name) {
  return `<i data-lucide="${name}"></i>`;
}

function refreshIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("visible");
  window.setTimeout(() => els.toast.classList.remove("visible"), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

function selectedEntity() {
  return state.entities.find((entity) => entity.urn === els.entity.value);
}

function populateEntities() {
  els.entity.innerHTML = state.entities
    .filter((entity) => entity.fields.length > 0)
    .map(
      (entity) =>
        `<option value="${entity.urn}">${entity.platform} / ${entity.name}</option>`,
    )
    .join("");

  const rawOrders = state.entities.find((entity) => entity.name === "raw_orders");
  if (rawOrders) els.entity.value = rawOrders.urn;
  populateFields();
}

function populateFields() {
  const entity = selectedEntity();
  if (!entity) return;
  els.field.innerHTML = entity.fields
    .map((field) => `<option value="${field.name}">${field.name} · ${field.type}</option>`)
    .join("");
  if (entity.fields.some((field) => field.name === "total_amount")) {
    els.field.value = "total_amount";
  }
  renderSourceContext(entity);
}

function renderSourceContext(entity) {
  els.sourceContext.innerHTML = `
    <div class="context-row"><span>Platform</span><strong>${entity.platform}</strong></div>
    <div class="context-row"><span>Owner</span><strong>${entity.owner || "Unassigned"}</strong></div>
    <div class="context-row"><span>Domain</span><strong>${entity.domain || "Unassigned"}</strong></div>
    <div class="context-row"><span>Criticality</span><strong>${entity.criticality.replace("_", " ")}</strong></div>
    <div class="context-row"><span>Schema fields</span><strong>${entity.fields.length}</strong></div>
  `;
}

function toggleConditionalFields() {
  els.newNameGroup.classList.toggle("hidden", els.changeType.value !== "rename_column");
  els.newTypeGroup.classList.toggle("hidden", els.changeType.value !== "change_type");
}

function riskDecision(level) {
  const labels = {
    low: ["Release with checks", "Standard validation is sufficient", "badge-check"],
    medium: ["Review required", "Coordinate downstream owners", "triangle-alert"],
    high: ["Hold deployment", "Repairs must land before release", "octagon-alert"],
    critical: ["Block deployment", "Executive approval and staged rollout", "shield-alert"],
  };
  return labels[level] || labels.medium;
}

function renderAnalysis(result) {
  state.analysis = result;
  const [title, subtitle, iconName] = riskDecision(result.risk_level);
  els.score.className = `risk-score ${result.risk_level}`;
  els.score.innerHTML = `<strong>${result.risk_score}</strong><span>/100</span>`;
  els.decision.className = `decision-banner ${result.risk_level}`;
  els.decision.innerHTML = `
    ${icon(iconName)}
    <div><strong>${title}</strong><span>${subtitle}</span></div>
  `;
  els.summary.textContent = result.summary;

  const owners = new Set(
    result.impacted_entities.filter((item) => item.owner).map((item) => item.owner),
  );
  const unowned = result.impacted_entities.filter((item) => !item.owner).length;
  els.assetCount.textContent = result.impacted_entities.length;
  els.ownerCount.textContent = owners.size;
  els.unownedCount.textContent = unowned;
  els.impactCount.textContent = result.impacted_entities.length;
  els.graphTitle.textContent = `${result.source.name}.${result.request.field}`;
  els.writeback.disabled = false;

  renderImpactList(result.impacted_entities);
  renderTrace(result.trace);
  renderPlan(result.plan);
  renderArtifacts(result.artifacts);
  renderGraph(result);
  refreshIcons();
}

function renderImpactList(impacts) {
  if (!impacts.length) {
    els.impactList.innerHTML = `
      <div class="empty-state compact">${icon("badge-check")}<span>No field-level consumers</span></div>
    `;
    return;
  }
  els.impactList.innerHTML = impacts
    .map(
      (item) => `
        <article class="impact-item">
          <div class="impact-topline">
            <span class="impact-name">${item.name}</span>
            <span class="criticality-chip ${item.criticality}">
              ${item.criticality.replace("_", " ")}
            </span>
          </div>
          <div class="impact-meta">
            <span>${item.platform} · depth ${item.depth}</span>
            <span>${item.owner || "Owner missing"}</span>
          </div>
          <div class="impact-fields">${item.impacted_fields.join(", ") || "operational dependency"}</div>
        </article>
      `,
    )
    .join("");
}

function renderTrace(trace) {
  els.traceCount.textContent = `${trace.length} stages`;
  els.traceList.innerHTML = trace
    .map(
      (item) => `
        <div class="trace-item">
          <strong>${item.stage}</strong>
          <span title="${item.detail}">${item.detail}</span>
        </div>
      `,
    )
    .join("");
}

function renderPlan(plan) {
  els.planList.innerHTML = plan
    .map(
      (step) => `
        <article class="plan-step">
          <span class="plan-order">${String(step.order).padStart(2, "0")}</span>
          <div class="plan-copy">
            <strong>${step.title}</strong>
            <p>${step.description}</p>
            <div class="plan-footer">
              <span>${step.owner}</span>
              <span class="status-chip ${step.status}">${step.status}</span>
            </div>
          </div>
        </article>
      `,
    )
    .join("");
}

function artifactIcon(language) {
  return {
    sql: "database",
    yaml: "braces",
    markdown: "file-text",
  }[language] || "file-code";
}

function renderArtifacts(artifacts) {
  state.selectedArtifact = 0;
  els.artifactTabs.innerHTML = artifacts
    .map(
      (artifact, index) => `
        <button class="artifact-tab ${index === 0 ? "active" : ""}" data-index="${index}">
          ${icon(artifactIcon(artifact.language))}
          <span>${artifact.path}</span>
        </button>
      `,
    )
    .join("");
  els.copy.disabled = false;
  els.download.disabled = false;
  selectArtifact(0);

  els.artifactTabs.querySelectorAll(".artifact-tab").forEach((button) => {
    button.addEventListener("click", () => selectArtifact(Number(button.dataset.index)));
  });
}

function selectArtifact(index) {
  if (!state.analysis) return;
  state.selectedArtifact = index;
  const artifact = state.analysis.artifacts[index];
  els.artifactCode.textContent = artifact.content;
  els.artifactTabs.querySelectorAll(".artifact-tab").forEach((tab, tabIndex) => {
    tab.classList.toggle("active", tabIndex === index);
  });
}

function renderGraph(result) {
  els.graph.innerHTML = "";
  const sourceUrn = result.source.urn;
  const elements = [
    ...result.graph.nodes.map((node) => {
      const classes = [];
      if (node.urn === sourceUrn) classes.push("source-node");
      if (["high", "mission_critical"].includes(node.criticality)) {
        classes.push("critical-node");
      }
      return {
        classes: classes.join(" "),
        data: {
          id: node.urn,
          label: node.name,
          subtitle: node.platform,
          criticality: node.criticality,
        },
      };
    }),
    ...result.graph.edges.map((edge) => ({
      data: {
        id: `${edge.source}->${edge.target}`,
        source: edge.source,
        target: edge.target,
        label: edge.relationship,
      },
    })),
  ];

  state.graph = cytoscape({
    container: els.graph,
    elements,
    layout: {
      name: "breadthfirst",
      directed: true,
      roots: [sourceUrn],
      spacingFactor: 1.45,
      padding: 35,
    },
    style: [
      {
        selector: "node",
        style: {
          width: 150,
          height: 54,
          shape: "round-rectangle",
          "background-color": "#147d64",
          "border-width": 2,
          "border-color": "#0d5d4a",
          label: "data(label)",
          color: "#ffffff",
          "font-family": "Inter",
          "font-size": 10,
          "font-weight": 600,
          "text-wrap": "ellipsis",
          "text-max-width": 130,
          "text-valign": "center",
          "text-halign": "center",
        },
      },
      {
        selector: "node.critical-node",
        style: {
          "background-color": "#b56c09",
          "border-color": "#8b5206",
        },
      },
      {
        selector: "node.source-node",
        style: {
          "background-color": "#c43d3d",
          "border-color": "#922b2b",
          width: 164,
          height: 60,
        },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "#9daaa4",
          "target-arrow-color": "#9daaa4",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(label)",
          color: "#67736e",
          "font-size": 8,
          "text-background-color": "#fbfcfb",
          "text-background-opacity": 1,
          "text-background-padding": 3,
        },
      },
    ],
  });
}

async function runAnalysis(event) {
  event.preventDefault();
  els.analyze.disabled = true;
  els.analyze.innerHTML = `${icon("loader-circle")}<span>Analyzing lineage</span>`;
  refreshIcons();

  const payload = {
    entity_urn: els.entity.value,
    field: els.field.value,
    change_type: els.changeType.value,
    new_name: els.changeType.value === "rename_column" ? els.newName.value : null,
    new_type: els.changeType.value === "change_type" ? els.newType.value : null,
    rationale: els.rationale.value,
  };

  try {
    const result = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderAnalysis(result);
    showToast(`Preflight ${result.analysis_id} completed`);
  } catch (error) {
    showToast(error.message);
  } finally {
    els.analyze.disabled = false;
    els.analyze.innerHTML = `${icon("scan-search")}<span>Run preflight</span>`;
    refreshIcons();
  }
}

async function applyWriteback() {
  if (!state.analysis) return;
  els.writeback.disabled = true;
  try {
    const result = await api(`/api/analyses/${state.analysis.analysis_id}/apply`, {
      method: "POST",
      body: JSON.stringify({
        approved_by: "Demo reviewer",
        note: "Approved from the ChangeGuard review workspace.",
      }),
    });
    els.writeback.innerHTML = `${icon("badge-check")}<span>Writeback recorded</span>`;
    showToast(result.message);
    refreshIcons();
  } catch (error) {
    els.writeback.disabled = false;
    showToast(error.message);
  }
}

async function copyArtifact() {
  if (!state.analysis) return;
  const artifact = state.analysis.artifacts[state.selectedArtifact];
  await navigator.clipboard.writeText(artifact.content);
  showToast("Artifact copied");
}

function downloadArtifact() {
  if (!state.analysis) return;
  const artifact = state.analysis.artifacts[state.selectedArtifact];
  const blob = new Blob([artifact.content], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = artifact.path.split("/").pop();
  link.click();
  URL.revokeObjectURL(link.href);
}

async function initialize() {
  try {
    const [status, entities] = await Promise.all([api("/api/status"), api("/api/entities")]);
    state.entities = entities;
    els.mode.textContent = `${status.mode} metadata · ${status.llm_enabled ? "LLM on" : "deterministic"}`;
    populateEntities();
  } catch (error) {
    els.mode.textContent = "Connection failed";
    showToast(error.message);
  }
  toggleConditionalFields();
  refreshIcons();
}

els.form.addEventListener("submit", runAnalysis);
els.entity.addEventListener("change", populateFields);
els.changeType.addEventListener("change", toggleConditionalFields);
els.writeback.addEventListener("click", applyWriteback);
els.copy.addEventListener("click", copyArtifact);
els.download.addEventListener("click", downloadArtifact);
els.refresh.addEventListener("click", initialize);

initialize();
