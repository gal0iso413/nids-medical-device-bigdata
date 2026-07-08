const FALLBACK_DATA = {
  meta: { title: "Class 1 Meeting UI Prototype", anchors: ["202605"] },
  scenarios: [],
};

const TYPE_COLOR = {
  제조사: "#4c78a8",
  유통사: "#f58518",
  병원: "#54a24b",
};

const TYPE_X = { 제조사: 90, 유통사: 320, 병원: 580 };

const state = {
  data: null,
  scenarioId: null,
  anchorMonth: null,
  topN: 8,
  showHospital: true,
  viewMode: "overview",
  focalId: null,
  searchQuery: "",
};

const dom = {
  anchorMonth: document.getElementById("anchorMonth"),
  scenarioSelect: document.getElementById("scenarioSelect"),
  viewMode: document.getElementById("viewMode"),
  topNRange: document.getElementById("topNRange"),
  topNValue: document.getElementById("topNValue"),
  hospitalToggle: document.getElementById("hospitalToggle"),
  reloadBtn: document.getElementById("reloadBtn"),
  scenarioDescription: document.getElementById("scenarioDescription"),
  tabs: document.querySelectorAll(".tab-btn"),
  sections: document.querySelectorAll(".section"),
  searchPanel: document.getElementById("searchPanel"),
  entitySearch: document.getElementById("entitySearch"),
  entitySelect: document.getElementById("entitySelect"),
  searchMeta: document.getElementById("searchMeta"),
  networkSvg: document.getElementById("networkSvg"),
  graphTitle: document.getElementById("graphTitle"),
  graphCaption: document.getElementById("graphCaption"),
  focalDetail: document.getElementById("focalDetail"),
};

async function loadData() {
  try {
    const response = await fetch("./data/mock_data.json");
    if (!response.ok) throw new Error("mock_data.json not found");
    return await response.json();
  } catch (error) {
    console.warn("Failed to load mock data:", error);
    return FALLBACK_DATA;
  }
}

function getScenariosByAnchor(anchorMonth) {
  return (state.data?.scenarios || []).filter((s) => s.anchorMonth === anchorMonth);
}

function getCurrentScenario() {
  const scenarios = getScenariosByAnchor(state.anchorMonth);
  return scenarios.find((s) => s.id === state.scenarioId) || scenarios[0] || null;
}

function getGraph(scenario) {
  return scenario?.network?.graph || { nodes: [], edges: [] };
}

function fillSelectOptions(selectElement, values, labelFormatter) {
  selectElement.innerHTML = "";
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labelFormatter(value);
    selectElement.appendChild(option);
  });
}

function formatStatusClass(text) {
  if (!text) return "";
  if (text.includes("낮음") || text.includes("안정")) return "status-good";
  if (text.includes("관찰") || text.includes("주의")) return "status-warn";
  if (text.includes("경고") || text.includes("높음")) return "status-danger";
  return "";
}

function renderCards(containerId, cards) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  (cards || []).forEach((card) => {
    const cardElement = document.createElement("article");
    cardElement.className = "card";
    cardElement.innerHTML = `
      <p class="card-label">${card.label}</p>
      <p class="card-value">${card.value}</p>
      <p class="card-note">${card.note}</p>
    `;
    container.appendChild(cardElement);
  });
}

function renderTable(bodyId, rows, columns) {
  const tableBody = document.getElementById(bodyId);
  tableBody.innerHTML = "";
  (rows || []).forEach((row) => {
    const tr = document.createElement("tr");
    if (row.entityId) tr.dataset.entityId = row.entityId;
    columns.forEach((column) => {
      const td = document.createElement("td");
      const rawValue = row[column.key];
      const value = rawValue === undefined || rawValue === null ? "-" : rawValue;
      td.textContent = value;
      if (column.status) td.className = formatStatusClass(String(value));
      tr.appendChild(td);
    });
    tableBody.appendChild(tr);
  });
}

function nodeById(graph) {
  return Object.fromEntries(graph.nodes.map((n) => [n.id, n]));
}

function buildAdjacency(graph) {
  const inMap = {};
  const outMap = {};
  graph.nodes.forEach((n) => {
    inMap[n.id] = [];
    outMap[n.id] = [];
  });
  graph.edges.forEach((e) => {
    if (outMap[e.src]) outMap[e.src].push(e);
    if (inMap[e.dst]) inMap[e.dst].push(e);
  });
  return { inMap, outMap };
}

function egoSubgraph(graph, focalId, hops = 1) {
  const nodeIds = new Set([focalId]);
  let frontier = new Set([focalId]);
  for (let h = 0; h < hops; h += 1) {
    const next = new Set();
    graph.edges.forEach((e) => {
      if (frontier.has(e.src)) next.add(e.dst);
      if (frontier.has(e.dst)) next.add(e.src);
    });
    next.forEach((id) => nodeIds.add(id));
    frontier = next;
  }
  if (!state.showHospital) {
    graph.nodes.forEach((n) => {
      if (n.type === "병원" && n.id !== focalId) nodeIds.delete(n.id);
    });
  }
  const nodes = graph.nodes.filter((n) => nodeIds.has(n.id));
  const edges = graph.edges.filter((e) => nodeIds.has(e.src) && nodeIds.has(e.dst));
  return { nodes, edges };
}

function overviewSubgraph(graph) {
  const distributors = graph.nodes
    .filter((n) => n.type === "유통사")
    .sort((a, b) => b.gnnScore - a.gnnScore)
    .slice(0, state.topN);
  const seed = new Set(distributors.map((n) => n.id));
  graph.edges.forEach((e) => {
    if (seed.has(e.src) || seed.has(e.dst)) {
      seed.add(e.src);
      seed.add(e.dst);
    }
  });
  if (!state.showHospital) {
    graph.nodes.forEach((n) => {
      if (n.type === "병원") seed.delete(n.id);
    });
  }
  return {
    nodes: graph.nodes.filter((n) => seed.has(n.id)),
    edges: graph.edges.filter((e) => seed.has(e.src) && seed.has(e.dst)),
  };
}

function layoutNodes(nodes) {
  const groups = { 제조사: [], 유통사: [], 병원: [] };
  nodes.forEach((n) => {
    if (groups[n.type]) groups[n.type].push(n);
  });
  const positions = {};
  Object.entries(groups).forEach(([type, list]) => {
    const sorted = [...list].sort((a, b) => a.name.localeCompare(b.name, "ko"));
    const step = 430 / Math.max(sorted.length, 1);
    sorted.forEach((node, idx) => {
      positions[node.id] = {
        x: TYPE_X[type] || 320,
        y: 40 + step * idx + step / 2,
      };
    });
  });
  return positions;
}

function clearSvg() {
  while (dom.networkSvg.firstChild) dom.networkSvg.removeChild(dom.networkSvg.firstChild);
}

function renderNetworkSvg(subgraph, focalId = null) {
  clearSvg();
  const { nodes, edges } = subgraph;
  if (!nodes.length) {
    dom.graphCaption.textContent = "표시할 네트워크가 없습니다.";
    return;
  }

  const positions = layoutNodes(nodes);
  const posById = (id) => positions[id] || { x: 360, y: 240 };

  const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  edgeLayer.setAttribute("class", "edge-layer");
  edges.forEach((e) => {
    const p1 = posById(e.src);
    const p2 = posById(e.dst);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", String(p1.x));
    line.setAttribute("y1", String(p1.y));
    line.setAttribute("x2", String(p2.x));
    line.setAttribute("y2", String(p2.y));
    line.setAttribute("class", "edge-line");
    edgeLayer.appendChild(line);
  });
  dom.networkSvg.appendChild(edgeLayer);

  const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  nodeLayer.setAttribute("class", "node-layer");
  nodes.forEach((node) => {
    const p = posById(node.id);
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "node-group");
    g.dataset.entityId = node.id;

    const radius = node.id === focalId ? 14 : 8 + Math.min(node.gnnScore / 12, 8);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", String(p.x));
    circle.setAttribute("cy", String(p.y));
    circle.setAttribute("r", String(radius));
    circle.setAttribute("fill", TYPE_COLOR[node.type] || "#aec7e8");
    if (node.id === focalId) circle.setAttribute("stroke", "#6a1b9a");
    else if (node.risk === "경고") circle.setAttribute("stroke", "#b42318");
    else circle.setAttribute("stroke", "#ffffff");
    circle.setAttribute("stroke-width", node.id === focalId ? "3" : "1.5");

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", String(p.x));
    label.setAttribute("y", String(p.y + radius + 12));
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", "node-label");
    label.textContent = node.name;

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${node.name} | ${node.type} | AI ${node.gnnScore}`;

    g.appendChild(title);
    g.appendChild(circle);
    g.appendChild(label);
    g.addEventListener("click", () => {
      state.focalId = node.id;
      if (state.viewMode !== "search") {
        state.viewMode = "search";
        dom.viewMode.value = "search";
        dom.searchPanel.classList.remove("hidden");
      }
      dom.entitySearch.value = node.name;
      updateEntitySelectOptions();
      renderScenario();
    });
    nodeLayer.appendChild(g);
  });
  dom.networkSvg.appendChild(nodeLayer);

  dom.graphCaption.textContent = `${nodes.length}개 기관 · ${edges.length}개 연결` +
    (focalId ? ` · 선택: ${nodeById(getGraph(getCurrentScenario()))[focalId]?.name || focalId}` : "");
}

function renderFocalDetail(graph, focalId) {
  if (!focalId) {
    dom.focalDetail.innerHTML = '<p class="muted">업체를 선택하면 연결 정보가 표시됩니다.</p>';
    return;
  }
  const node = nodeById(graph)[focalId];
  if (!node) {
    dom.focalDetail.innerHTML = '<p class="muted">선택한 업체를 찾을 수 없습니다.</p>';
    return;
  }
  const { inMap, outMap } = buildAdjacency(graph);
  dom.focalDetail.innerHTML = `
    <p><strong>${node.name}</strong> <span class="chip">${node.type}</span></p>
    <p>AI 점수: <strong class="${formatStatusClass(node.risk)}">${node.gnnScore}</strong> (${node.risk})</p>
    <p>유입 연결: <strong>${inMap[focalId]?.length || 0}</strong> · 유출 연결: <strong>${outMap[focalId]?.length || 0}</strong></p>
  `;
}

function updateEntitySelectOptions() {
  const scenario = getCurrentScenario();
  const graph = getGraph(scenario);
  const q = state.searchQuery.trim().toLowerCase();
  const filtered = graph.nodes.filter((n) => !q || n.name.toLowerCase().includes(q));
  dom.entitySelect.innerHTML = "";
  filtered.slice(0, 80).forEach((node) => {
    const opt = document.createElement("option");
    opt.value = node.id;
    opt.textContent = `${node.name} (${node.type}) · AI ${node.gnnScore}`;
    dom.entitySelect.appendChild(opt);
  });
  dom.searchMeta.textContent = `${filtered.length}개 검색됨`;
  if (filtered.length && (!state.focalId || !filtered.some((n) => n.id === state.focalId))) {
    state.focalId = filtered[0].id;
  }
  if (state.focalId) dom.entitySelect.value = state.focalId;
}

function renderNetworkSection(scenario) {
  const graph = getGraph(scenario);
  renderCards("networkCards", scenario.network.cards);

  const isSearch = state.viewMode === "search";
  dom.searchPanel.classList.toggle("hidden", !isSearch);
  dom.graphTitle.textContent = isSearch ? "업체 연결망 (Ego Network)" : "AI 상위 유통사 연결 개요";

  if (isSearch) {
    updateEntitySelectOptions();
    const subgraph = state.focalId ? egoSubgraph(graph, state.focalId, 1) : { nodes: [], edges: [] };
    renderNetworkSvg(subgraph, state.focalId);
    renderFocalDetail(graph, state.focalId);
  } else {
    const subgraph = overviewSubgraph(graph);
    const hubId = scenario.network.hubEntityId || subgraph.nodes.find((n) => n.type === "유통사")?.id;
    state.focalId = hubId || null;
    renderNetworkSvg(subgraph, hubId);
    renderFocalDetail(graph, hubId);
  }

  const tableRows = isSearch && state.focalId
    ? graph.edges
        .filter((e) => e.src === state.focalId || e.dst === state.focalId)
        .slice(0, 20)
        .map((e) => {
          const src = nodeById(graph)[e.src];
          const dst = nodeById(graph)[e.dst];
          const note = src?.risk === "경고" || dst?.risk === "경고" ? "우선 확인" : "연결";
          return { supplier: src?.name, receiver: dst?.name, item: e.item, note };
        })
    : scenario.network.table;

  renderTable("networkTableBody", tableRows, [
    { key: "supplier" },
    { key: "receiver" },
    { key: "item" },
    { key: "note" },
  ]);
}

function renderScenario() {
  const scenario = getCurrentScenario();
  if (!scenario) {
    dom.scenarioDescription.textContent = "선택한 기준월에 시나리오가 없습니다.";
    return;
  }

  dom.scenarioDescription.textContent = scenario.description;
  renderNetworkSection(scenario);

  renderCards("gnnCards", scenario.gnn.cards);
  renderTable("gnnTableBody", scenario.gnn.rows.slice(0, state.topN), [
    { key: "entity" },
    { key: "score" },
    { key: "status", status: true },
    { key: "reason" },
  ]);

  document.querySelectorAll("#gnnTableBody tr").forEach((row) => {
    row.style.cursor = "pointer";
    row.addEventListener("click", () => {
      const entityId = row.dataset.entityId;
      if (!entityId) return;
      state.viewMode = "search";
      state.focalId = entityId;
      dom.viewMode.value = "search";
      dom.searchPanel.classList.remove("hidden");
      setActiveSection("network");
      dom.tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.target === "network"));
      renderScenario();
    });
  });
}

function setActiveSection(sectionId) {
  dom.tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.target === sectionId));
  dom.sections.forEach((section) => section.classList.toggle("active", section.id === `section-${sectionId}`));
}

function setScenarioOptions() {
  const scenarios = getScenariosByAnchor(state.anchorMonth);
  fillSelectOptions(dom.scenarioSelect, scenarios.map((s) => s.id), (id) => {
    const scenario = scenarios.find((s) => s.id === id);
    return scenario ? scenario.name : id;
  });
  state.scenarioId = scenarios[0]?.id || null;
  state.focalId = null;
}

function bindEvents() {
  dom.anchorMonth.addEventListener("change", (event) => {
    state.anchorMonth = event.target.value;
    setScenarioOptions();
    renderScenario();
  });

  dom.scenarioSelect.addEventListener("change", (event) => {
    state.scenarioId = event.target.value;
    state.focalId = null;
    renderScenario();
  });

  dom.viewMode.addEventListener("change", (event) => {
    state.viewMode = event.target.value;
    renderScenario();
  });

  dom.topNRange.addEventListener("input", (event) => {
    state.topN = Number(event.target.value);
    dom.topNValue.textContent = String(state.topN);
    renderScenario();
  });

  dom.hospitalToggle.addEventListener("change", (event) => {
    state.showHospital = event.target.checked;
    renderScenario();
  });

  dom.entitySearch.addEventListener("input", (event) => {
    state.searchQuery = event.target.value;
    updateEntitySelectOptions();
    renderScenario();
  });

  dom.entitySelect.addEventListener("change", (event) => {
    state.focalId = event.target.value;
    renderScenario();
  });

  dom.reloadBtn.addEventListener("click", async () => {
    state.data = await loadData();
    initializeSelectors();
    renderScenario();
  });

  dom.tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActiveSection(tab.dataset.target));
  });
}

function initializeSelectors() {
  const anchors = state.data?.meta?.anchors || [];
  fillSelectOptions(dom.anchorMonth, anchors, (anchor) => `${anchor.slice(0, 4)}년 ${anchor.slice(4)}월`);
  state.anchorMonth = anchors[0] || null;
  setScenarioOptions();
}

async function init() {
  state.data = await loadData();
  initializeSelectors();
  bindEvents();
  renderScenario();
}

init();
