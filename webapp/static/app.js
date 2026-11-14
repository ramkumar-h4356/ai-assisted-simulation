(() => {
  "use strict";

  const state = { workspaces: [], activeId: null, detail: null, replay: null, replayStep: 0, selectedAgentId: null, replayTimer: null, replayPlaying: false, nodeHits: [] };
  const $ = (id) => document.getElementById(id);

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  }

  async function api(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const message = body && typeof body === "object" ? body.detail : body;
      throw new Error(message || `Request failed (${response.status})`);
    }
    return body;
  }

  function notice(message, error = false) {
    const box = $("notice");
    box.textContent = message;
    box.classList.toggle("error", error);
    box.hidden = false;
    window.clearTimeout(notice.timer);
    notice.timer = window.setTimeout(() => { box.hidden = true; }, 6500);
  }

  function showResult(title, payload, downloadUrl = null, linkLabel = "Download generated artifact ↓") {
    $("result-title").textContent = title;
    const output = JSON.stringify(payload, null, 2);
    $("result-output").textContent = output.length > 18000 ? `${output.slice(0, 18000)}\n… output truncated in this panel` : output;
    const link = $("result-download");
    if (downloadUrl) {
      link.href = downloadUrl;
      link.textContent = linkLabel;
      link.target = downloadUrl.includes("/preview") ? "_blank" : "_self";
      link.rel = "noopener noreferrer";
      link.hidden = false;
    } else {
      link.removeAttribute("href");
      link.hidden = true;
    }
    $("result-panel").hidden = false;
    $("result-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function progressPercent(overview) {
    const stages = overview.stages || [];
    if (!stages.length) return 0;
    return Math.round(stages.filter((item) => item.status === "completed").length / stages.length * 100);
  }

  async function loadWorkspaces(selectId = state.activeId) {
    const payload = await api("/api/v1/workspaces");
    state.workspaces = payload.workspaces || [];
    $("project-count").textContent = String(state.workspaces.length);
    const list = $("workspace-list");
    list.replaceChildren();
    if (!state.workspaces.length) {
      list.append(node("p", "muted small", "No saved workspaces yet."));
    }
    for (const workspace of state.workspaces) {
      const button = node("button", `workspace-item${workspace.workspace_id === state.activeId ? " active" : ""}`);
      button.type = "button";
      button.addEventListener("click", () => selectWorkspace(workspace.workspace_id));
      button.append(node("strong", "", workspace.title));
      button.append(node("small", "", `${workspace.workspace_id} · ${workspace.artifact_count} artifacts`));
      const track = node("div", "mini-progress");
      const fill = node("span");
      fill.style.width = `${progressPercent(workspace)}%`;
      track.append(fill);
      button.append(track);
      list.append(button);
    }
    if (selectId && state.workspaces.some((item) => item.workspace_id === selectId)) {
      await selectWorkspace(selectId, false);
    } else if (!state.activeId && state.workspaces.length) {
      await selectWorkspace(state.workspaces[0].workspace_id, false);
    }
  }

  async function selectWorkspace(workspaceId, refreshList = true) {
    if (state.activeId !== workspaceId) clearReplay();
    state.activeId = workspaceId;
    state.detail = await api(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}`);
    renderWorkspace();
    if (refreshList) await loadWorkspaces(workspaceId);
    else {
      document.querySelectorAll(".workspace-item").forEach((item) => item.classList.remove("active"));
      const buttons = [...document.querySelectorAll(".workspace-item")];
      const index = state.workspaces.findIndex((item) => item.workspace_id === workspaceId);
      if (buttons[index]) buttons[index].classList.add("active");
    }
  }

  function fillSelect(id, artifacts, type, placeholder) {
    const select = $(id);
    const current = select.value;
    select.replaceChildren();
    const first = node("option", "", placeholder || "Select an artifact");
    first.value = "";
    select.append(first);
    for (const item of artifacts.filter((artifact) => artifact.artifact_type === type)) {
      const option = node("option", "", `${item.display_name} · ${item.artifact_id}`);
      option.value = item.artifact_id;
      select.append(option);
    }
    if ([...select.options].some((item) => item.value === current)) select.value = current;
  }

  function renderWorkspace() {
    const detail = state.detail;
    if (!detail) return;
    const overview = detail.overview;
    const artifacts = detail.artifacts || [];
    $("empty-state").hidden = true;
    $("workspace-view").hidden = false;
    $("active-title").textContent = overview.title;
    $("active-id").textContent = `${overview.workspace_id}${overview.idea_project_id ? ` · Project ${overview.idea_project_id}` : " · Conceptual model not linked"}`;
    $("original-idea").textContent = detail.original_idea;
    $("stats-grid").replaceChildren();
    const completed = overview.stages.filter((item) => item.status === "completed").length;
    const stats = [["ARTIFACTS", overview.artifact_count], ["WORKFLOW STAGES", `${completed}/${overview.stages.length}`], ["UPDATED", new Date(overview.updated_at).toLocaleString()]];
    for (const [label, value] of stats) {
      const card = node("div", "stat-card");
      card.append(node("span", "", label), node("strong", "", value));
      $("stats-grid").append(card);
    }
    $("workflow-summary").textContent = `${completed} of ${overview.stages.length} stages completed`;
    $("workflow-grid").replaceChildren();
    for (const stage of overview.stages) {
      const card = node("div", `stage-card ${stage.status}`);
      const title = node("strong");
      title.append(node("span", "stage-dot"), document.createTextNode(stage.title));
      card.append(title, node("small", "", `${stage.status.replaceAll("_", " ")} · ${stage.artifact_count} artifacts`));
      $("workflow-grid").append(card);
    }
    $("artifact-count").textContent = String(artifacts.length);
    $("artifact-list").replaceChildren();
    if (!artifacts.length) $("artifact-list").append(node("p", "muted small", "No artifacts have been imported or generated."));
    for (const artifact of [...artifacts].reverse()) {
      const row = node("div", "artifact-row");
      row.append(node("span", "file-icon", artifact.artifact_type.split("_").map((part) => part[0]).join("").slice(0, 3).toUpperCase()));
      const info = node("div", "artifact-info");
      info.append(node("strong", "", artifact.display_name));
      info.append(node("small", "", `${artifact.artifact_type} · ${artifact.size_bytes.toLocaleString()} bytes · ${artifact.sha256.slice(0, 12)}…`));
      row.append(info);
      const link = node("a", "artifact-download", "↓");
      link.href = `/api/v1/workspaces/${encodeURIComponent(state.activeId)}/artifacts/${encodeURIComponent(artifact.artifact_id)}/download`;
      link.title = "Download original artifact";
      row.append(link);
      $("artifact-list").append(row);
    }
    $("activity-list").replaceChildren();
    const events = overview.recent_activity || [];
    if (!events.length) $("activity-list").append(node("p", "muted small", "No activity recorded."));
    for (const event of events) {
      const row = node("div", "activity-row");
      row.append(node("span", "activity-marker"));
      const info = node("div", "activity-info");
      info.append(node("strong", "", event.action.replaceAll("_", " ")));
      info.append(node("p", "", event.detail));
      info.append(node("small", "", new Date(event.occurred_at).toLocaleString()));
      row.append(info);
      $("activity-list").append(row);
    }
    fillSelect("profile-select", artifacts, "compilation_profile", "Select M8 profile");
    fillSelect("compilation-select", artifacts, "compilation_artifact", "Select compiled specification");
    fillSelect("sweep-compilation", artifacts, "compilation_artifact", "Select compiled specification");
    fillSelect("uncertainty-compilation", artifacts, "compilation_artifact", "Select compiled specification");
    fillSelect("analysis-execution", artifacts, "execution_result", "Select M9 execution result");
    fillSelect("visualization-execution", artifacts, "execution_result", "Select M9 execution result");
    fillSelect("uncertainty-plan", artifacts, "uncertainty_plan", "Select M11 plan");
    fillSelect("visualization-analysis", artifacts, "analysis_report", "No M10 analysis");
    fillSelect("visualization-uncertainty", artifacts, "uncertainty_report", "No M11 report");
    fillSelect("replay-execution", artifacts, "execution_result", "Select an ABM execution result");
  }

  async function refreshActive() {
    if (!state.activeId) return;
    state.detail = await api(`/api/v1/workspaces/${encodeURIComponent(state.activeId)}`);
    renderWorkspace();
    await loadWorkspaces(state.activeId);
  }

  function showError(error) { notice(error.message || String(error), true); }

  function clearReplay() {
    if (state.replayTimer !== null) window.clearInterval(state.replayTimer);
    state.replayTimer = null;
    state.replayPlaying = false;
    state.replay = null;
    state.replayStep = 0;
    state.selectedAgentId = null;
    state.nodeHits = [];
    const panel = $("replay-workspace");
    if (panel) panel.hidden = true;
    const play = $("replay-play");
    if (play) play.textContent = "▶ Play";
  }

  function stateColor(value) {
    const palette = ["#70d6bd", "#8eb8ff", "#f0bd72", "#d69bf2", "#ef8f9a", "#8ed4e8", "#c2d98a", "#f1a66e"];
    let hash = 2166136261;
    for (const char of String(value)) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
    return palette[(hash >>> 0) % palette.length];
  }

  function currentReplayFrame() {
    if (!state.replay) return null;
    return state.replay.frames[state.replayStep] || null;
  }

  function setReplayStep(nextStep) {
    if (!state.replay) return;
    const last = state.replay.frames.length - 1;
    state.replayStep = Math.max(0, Math.min(last, Number(nextStep) || 0));
    renderReplayFrame();
  }

  function renderReplayInspector(frame) {
    const counts = frame.state_counts || {};
    const legend = $("replay-state-legend");
    legend.replaceChildren();
    for (const [name, count] of Object.entries(counts).sort((a, b) => a[0].localeCompare(b[0]))) {
      const row = node("div", "replay-state-item");
      const label = node("span");
      const swatch = node("span", "replay-state-swatch");
      swatch.style.background = stateColor(name);
      label.append(swatch, document.createTextNode(name));
      row.append(label, node("strong", "", count));
      legend.append(row);
    }
    if (!legend.childElementCount) legend.append(node("p", "muted small", "No agents in this frame."));

    const selected = frame.agents.find((agent) => agent.id === state.selectedAgentId) || frame.agents[0];
    const inspector = $("replay-agent-inspector");
    inspector.replaceChildren();
    if (!selected) {
      inspector.append(node("p", "muted small", "No agent selected."));
    } else {
      state.selectedAgentId = selected.id;
      const title = node("div", "replay-agent-title");
      title.append(node("strong", "", selected.id));
      if ((frame.changed_agents || []).some((item) => item.agent_id === selected.id)) {
        title.append(node("span", "replay-change-chip", "CHANGED"));
      }
      inspector.append(title, node("div", "replay-agent-type", selected.agent_type));
      const stateTag = node("span", "replay-agent-state", selected.state);
      stateTag.style.border = `1px solid ${stateColor(selected.state)}66`;
      inspector.append(stateTag);
      if (state.replay?.space && selected.position) {
        const coordinate = node(
          "div",
          "replay-agent-type",
          `Position: (${selected.position.x.toFixed(2)}, ${selected.position.y.toFixed(2)})`
        );
        inspector.append(coordinate);
      }
      const attributes = node("dl", "replay-attributes");
      const entries = Object.entries(selected.attributes || {}).sort((a, b) => a[0].localeCompare(b[0]));
      if (!entries.length) attributes.append(node("dt", "muted", "No attributes"));
      for (const [key, value] of entries) {
        attributes.append(node("dt", "", key), node("dd", "", typeof value === "object" ? JSON.stringify(value) : String(value)));
      }
      inspector.append(attributes);
    }

    const rules = $("replay-rule-list");
    rules.replaceChildren();
    const evaluations = frame.rule_evaluations || [];
    if (!evaluations.length) {
      rules.append(node("p", "muted small", "No rule evaluations recorded for this step."));
    } else {
      for (const item of evaluations) {
        const applied = Boolean(item.actions_applied);
        const row = node("div", `replay-rule-item ${applied ? "applied" : "skipped"}`);
        row.append(node("strong", "", `${item.agent_id} · ${item.rule_id}`));
        const outcome = !item.condition_matched ? "Condition did not match" : item.probability_passed === false ? "Probability check did not pass" : applied ? "Actions applied" : "Matched; no action applied";
        row.append(node("small", "", `${outcome} · ${item.state_before} → ${item.state_after}`));
        rules.append(row);
      }
    }
  }

  function drawReplay() {
    const replay = state.replay;
    const canvas = $("replay-canvas");
    if (!replay || !canvas || $("replay-workspace").hidden) return;
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 10 || rect.height < 10) return;
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const width = rect.width;
    const height = rect.height;
    ctx.clearRect(0, 0, width, height);
    const padX = Math.min(76, width * 0.12);
    const padY = Math.min(70, height * 0.12);
    const frame = currentReplayFrame();
    if (!frame) return;
    const current = new Map(frame.agents.map((agent) => [agent.id, agent]));
    const spatial = Boolean(replay.space);
    const position = new Map(replay.agents.map((agent) => {
      const data = current.get(agent.id);
      const normalized = spatial && data?.position
        ? {
            x: data.position.x / replay.space.width,
            y: data.position.y / replay.space.height,
          }
        : { x: agent.x, y: agent.y };
      return [agent.id, {
        x: padX + normalized.x * (width - padX * 2),
        y: padY + normalized.y * (height - padY * 2),
      }];
    }));
    const changedIds = new Set((frame.changed_agents || []).map((item) => item.agent_id));
    const radius = Math.max(10, Math.min(23, 30 - replay.agent_count * 0.12));
    state.nodeHits = [];

    if (spatial) {
      ctx.save();
      ctx.strokeStyle = "rgba(129, 159, 190, 0.20)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      for (let column = 1; column < 10; column += 1) {
        const x = padX + (width - padX * 2) * column / 10;
        ctx.beginPath(); ctx.moveTo(x, padY); ctx.lineTo(x, height - padY); ctx.stroke();
      }
      for (let row = 1; row < 8; row += 1) {
        const y = padY + (height - padY * 2) * row / 8;
        ctx.beginPath(); ctx.moveTo(padX, y); ctx.lineTo(width - padX, y); ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.strokeStyle = "rgba(155, 186, 213, 0.55)";
      ctx.strokeRect(padX, padY, width - padX * 2, height - padY * 2);
      ctx.restore();
    }

    // Relationships are drawn from the exact linked M8 specification.
    for (const edge of replay.relationships) {
      const from = position.get(edge.source);
      const to = position.get(edge.target);
      if (!from || !to) continue;
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.strokeStyle = "rgba(129, 159, 190, 0.48)";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      if (edge.directed) {
        const angle = Math.atan2(to.y - from.y, to.x - from.x);
        const tipX = to.x - Math.cos(angle) * (radius + 3);
        const tipY = to.y - Math.sin(angle) * (radius + 3);
        ctx.beginPath();
        ctx.moveTo(tipX, tipY);
        ctx.lineTo(tipX - Math.cos(angle - 0.48) * 9, tipY - Math.sin(angle - 0.48) * 9);
        ctx.lineTo(tipX - Math.cos(angle + 0.48) * 9, tipY - Math.sin(angle + 0.48) * 9);
        ctx.closePath();
        ctx.fillStyle = "rgba(155, 186, 213, 0.8)";
        ctx.fill();
      }
      if (width > 520 && edge.relation_type) {
        const midX = (from.x + to.x) / 2;
        const midY = (from.y + to.y) / 2;
        ctx.font = "10px system-ui";
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(178, 199, 221, 0.75)";
        ctx.fillText(edge.relation_type, midX, midY - 6);
      }
    }

    for (const meta of replay.agents) {
      const point = position.get(meta.id);
      const data = current.get(meta.id);
      if (!point || !data) continue;
      const color = stateColor(data.state);
      const selected = meta.id === state.selectedAgentId;
      if (changedIds.has(meta.id)) {
        ctx.beginPath();
        ctx.arc(point.x, point.y, radius + 8, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(255, 218, 128, 0.9)";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.18;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = selected ? "#ffffff" : color;
      ctx.lineWidth = selected ? 3 : 2;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(point.x, point.y, Math.max(3, radius * 0.24), 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.textAlign = "center";
      ctx.font = "600 11px system-ui";
      ctx.fillStyle = "#e5edf7";
      ctx.fillText(meta.id, point.x, point.y + radius + 17);
      ctx.font = "9px system-ui";
      ctx.fillStyle = "#94a9c1";
      ctx.fillText(data.state, point.x, point.y + radius + 30);
      state.nodeHits.push({ id: meta.id, x: point.x, y: point.y, radius: radius + 8 });
    }

    ctx.textAlign = "left";
    ctx.font = "10px system-ui";
    ctx.fillStyle = "rgba(148, 169, 193, 0.7)";
    const worldLabel = spatial
      ? `WORLD ${replay.space.width} × ${replay.space.height} ${replay.space.boundary} · `
      : "NETWORK LAYOUT · ";
    ctx.fillText(`${worldLabel}STEP ${frame.step}  ·  ${replay.model_name}`, 16, 20);
  }

  function renderReplayFrame() {
    const replay = state.replay;
    if (!replay) return;
    const frame = currentReplayFrame();
    if (!frame) return;
    $("replay-step").max = String(replay.frames.length - 1);
    $("replay-step").value = String(state.replayStep);
    $("replay-step-label").textContent = `${frame.step} / ${replay.total_steps}`;
    $("replay-agent-count").textContent = String(frame.agents.length);
    $("replay-edge-count").textContent = String(replay.relationship_count);
    $("replay-rule-count").textContent = String((frame.rule_evaluations || []).length);
    $("replay-model-name").textContent = replay.model_name;
    $("replay-run-meta").textContent = `Run ${replay.run_index} · Seed ${replay.seed === null ? "not recorded" : replay.seed} · ${replay.experiment_id}`;
    renderReplayInspector(frame);
    drawReplay();
  }

  async function loadReplay() {
    if (!state.activeId) throw new Error("Select a project workspace first");
    const artifactId = $("replay-execution").value;
    if (!artifactId) throw new Error("Select an M9 execution result first");
    const runIndex = Number($("replay-run-index").value || 1);
    if (!Number.isInteger(runIndex) || runIndex < 1 || runIndex > 100) throw new Error("Run number must be between 1 and 100");
    clearReplay();
    const payload = await api(`/api/v1/workspaces/${encodeURIComponent(state.activeId)}/executions/${encodeURIComponent(artifactId)}/replay?run_index=${runIndex}`);
    state.replay = payload;
    state.selectedAgentId = payload.agents.length ? payload.agents[0].id : null;
    $("replay-workspace").hidden = false;
    setReplayStep(0);
    notice(`Loaded ABM replay: ${payload.agent_count} agents across ${payload.total_steps} recorded steps.`);
  }

  function toggleReplayPlayback() {
    if (!state.replay) return;
    if (state.replayPlaying) {
      window.clearInterval(state.replayTimer);
      state.replayTimer = null;
      state.replayPlaying = false;
      $("replay-play").textContent = "▶ Play";
      return;
    }
    if (state.replayStep >= state.replay.total_steps) setReplayStep(0);
    state.replayPlaying = true;
    $("replay-play").textContent = "Ⅱ Pause";
    const tick = () => {
      if (!state.replay) return;
      if (state.replayStep >= state.replay.total_steps) {
        window.clearInterval(state.replayTimer);
        state.replayTimer = null;
        state.replayPlaying = false;
        $("replay-play").textContent = "▶ Play";
        return;
      }
      setReplayStep(state.replayStep + 1);
    };
    const delay = Math.max(120, 700 / Number($("replay-speed").value || 1));
    state.replayTimer = window.setInterval(tick, delay);
  }

  $("load-replay").addEventListener("click", () => loadReplay().catch(showError));
  $("replay-play").addEventListener("click", toggleReplayPlayback);
  $("replay-first").addEventListener("click", () => setReplayStep(0));
  $("replay-prev").addEventListener("click", () => setReplayStep(state.replayStep - 1));
  $("replay-next").addEventListener("click", () => setReplayStep(state.replayStep + 1));
  $("replay-last").addEventListener("click", () => setReplayStep(state.replay ? state.replay.total_steps : 0));
  $("replay-step").addEventListener("input", (event) => setReplayStep(event.currentTarget.value));
  $("replay-speed").addEventListener("change", () => {
    if (state.replayPlaying) { toggleReplayPlayback(); toggleReplayPlayback(); }
  });
  $("replay-canvas").addEventListener("click", (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = [...state.nodeHits].reverse().find((item) => Math.hypot(item.x - x, item.y - y) <= item.radius);
    if (hit) { state.selectedAgentId = hit.id; renderReplayFrame(); }
  });
  window.addEventListener("resize", drawReplay);

  $("create-workspace-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const created = await api("/api/v1/workspaces", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: form.get("title"), original_idea: form.get("original_idea") }),
      });
      event.currentTarget.reset();
      state.activeId = created.overview.workspace_id;
      await loadWorkspaces(state.activeId);
      notice("Workspace created. Its original idea is now captured in the project ledger.");
    } catch (error) { showError(error); }
  });

  $("refresh-workspaces").addEventListener("click", () => loadWorkspaces().catch(showError));

  $("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = $("artifact-file").files[0];
    if (!file || !state.activeId) return;
    const body = new FormData();
    body.append("file", file);
    const type = encodeURIComponent($("artifact-type").value);
    try {
      const result = await api(`/api/v1/workspaces/${encodeURIComponent(state.activeId)}/artifacts?artifact_type=${type}`, { method: "POST", body });
      await refreshActive();
      showResult("Artifact imported and validated", result.artifact);
      notice("Artifact added to the workspace ledger.");
      event.currentTarget.reset();
    } catch (error) { showError(error); }
  });

  $("readiness-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await api(`/api/v1/workspaces/${state.activeId}/readiness`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ selected_paradigm: $("readiness-paradigm").value || null }) });
      await refreshActive(); showResult("M7 readiness assessment", result);
    } catch (error) { showError(error); }
  });

  $("compile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await api(`/api/v1/workspaces/${state.activeId}/compile`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_artifact_id: $("profile-select").value }) });
      await refreshActive(); showResult("M8 compilation", result);
    } catch (error) { showError(error); }
  });

  $("execute-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const seedText = $("execution-seed").value;
      const result = await api(`/api/v1/workspaces/${state.activeId}/execute`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ compilation_artifact_id: $("compilation-select").value, runs: Number($("execution-runs").value), base_seed: seedText === "" ? null : Number(seedText) }) });
      await refreshActive(); showResult("M9 simulation execution", result);
    } catch (error) { showError(error); }
  });

  $("sweep-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const values = $("sweep-levels").value.split(",").map((item) => item.trim()).filter(Boolean).map((item) => {
        try { return JSON.parse(item); } catch { return item; }
      });
      const seedText = $("sweep-seed").value;
      const result = await api(`/api/v1/workspaces/${state.activeId}/parameter-sweep`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ compilation_artifact_id: $("sweep-compilation").value, factors: [{ target_path: $("sweep-path").value, levels: values }], runs: Number($("sweep-runs").value), base_seed: seedText === "" ? null : Number(seedText), include_baseline: true }) });
      await refreshActive(); showResult("M10 parameter sweep", result);
    } catch (error) { showError(error); }
  });

  $("analysis-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await api(`/api/v1/workspaces/${state.activeId}/analysis`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ execution_artifact_id: $("analysis-execution").value }) });
      await refreshActive(); showResult("M10 descriptive analysis", result);
    } catch (error) { showError(error); }
  });

  $("uncertainty-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const seedText = $("uncertainty-seed").value;
      const result = await api(`/api/v1/workspaces/${state.activeId}/uncertainty`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ compilation_artifact_id: $("uncertainty-compilation").value, plan_artifact_id: $("uncertainty-plan").value, execution_base_seed: seedText === "" ? null : Number(seedText) }) });
      await refreshActive(); showResult("M11 uncertainty and robustness", result);
    } catch (error) { showError(error); }
  });

  $("visualization-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await api(`/api/v1/workspaces/${state.activeId}/visualization`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ execution_artifact_id: $("visualization-execution").value, analysis_artifact_id: $("visualization-analysis").value || null, uncertainty_artifact_id: $("visualization-uncertainty").value || null }) });
      await refreshActive(); showResult("M12 dashboard generated", result, result.html_download_url);
    } catch (error) { showError(error); }
  });

  $("verify-button").addEventListener("click", async () => {
    try {
      const result = await api(`/api/v1/workspaces/${state.activeId}/verification`);
      showResult("Workspace integrity verification", result);
      notice(result.valid ? "All stored artifacts passed size and SHA-256 checks." : "One or more artifacts failed integrity verification.", !result.valid);
    } catch (error) { showError(error); }
  });

  $("export-button").addEventListener("click", async () => {
    try {
      const result = await api(`/api/v1/workspaces/${state.activeId}/export`, { method: "POST" });
      showResult("Workspace export created", result, result.download_url);
    } catch (error) { showError(error); }
  });

  $("close-result").addEventListener("click", () => { $("result-panel").hidden = true; });
  loadWorkspaces().catch(showError);
})();
