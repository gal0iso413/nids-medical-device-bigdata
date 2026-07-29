const state = {
  data: null,
  focalId: "D03",
  query: "C 유통",
  anchor: "202605",
  depth: 1,
  edgeMeasure: "count",
};

const COLORS = {
  제조사: "#2869aa",
  수입사: "#6b4ea0",
  유통사: "#c16a16",
  의료기관: "#2f7d4a",
};

const GRAPH_WIDTH = 980;
const LABEL_FONT_SIZE = 13;
const LABEL_LINE_HEIGHT = 18;
const LABEL_PAD = 6;

const X_BY_LANE = {
  공급원: 150,
  유통사: 490,
  의료기관: 830,
};

const elements = {
  search: document.getElementById("entitySearch"),
  entitySelect: document.getElementById("entitySelect"),
  searchCount: document.getElementById("searchCount"),
  anchor: document.getElementById("anchorMonth"),
  depthButtons: document.querySelectorAll("[data-depth]"),
  edgeMeasure: document.getElementById("edgeMeasure"),
  metrics: document.getElementById("metricGrid"),
  selectionDescription: document.getElementById("selectionDescription"),
  graphDescription: document.getElementById("graphDescription"),
  svg: document.getElementById("networkSvg"),
  detail: document.getElementById("entityDetail"),
  inboundBody: document.getElementById("inboundBody"),
  outboundBody: document.getElementById("outboundBody"),
  reviewBody: document.getElementById("reviewBody"),
  evidenceGrid: document.getElementById("evidenceGrid"),
  limitationList: document.getElementById("limitationList"),
  showMyCompanyButton: document.getElementById("showMyCompanyButton"),
  conclusionHeadline: document.getElementById("conclusionHeadline"),
  conclusionBody: document.getElementById("conclusionBody"),
  flowSteps: document.getElementById("flowSteps"),
  sectionOrient: document.getElementById("section-orient"),
  sectionChange: document.getElementById("section-change"),
  sectionCheck: document.getElementById("section-check"),
};

function gnnScore(node) {
  return node.gnnScore ?? node.reviewScore ?? 0;
}

function myCompanyId() {
  return state.data?.meta?.myCompanyId || "D03";
}

function nodeMap() {
  return new Map(state.data.nodes.map((node) => [node.id, node]));
}

function selectedMonths(anchor = state.anchor) {
  const months = state.data.meta.availableMonths.filter((month) => month <= anchor);
  return months.slice(-3);
}

function previousMonths() {
  const months = state.data.meta.availableMonths.filter((month) => month < selectedMonths()[0]);
  return months.slice(-3);
}

function aggregateEdge(edge, months = selectedMonths()) {
  return months.reduce(
    (total, month) => {
      const value = edge.monthly[month] || { count: 0, quantity: 0 };
      total.count += value.count;
      total.quantity += value.quantity;
      return total;
    },
    { count: 0, quantity: 0 },
  );
}

function incidentEdges(focalId = state.focalId) {
  return state.data.edges.filter((edge) => edge.src === focalId || edge.dst === focalId);
}

function subgraph(depth = state.depth) {
  const included = new Set([state.focalId]);
  let frontier = new Set([state.focalId]);

  for (let hop = 0; hop < depth; hop += 1) {
    const next = new Set();
    state.data.edges.forEach((edge) => {
      if (frontier.has(edge.src)) next.add(edge.dst);
      if (frontier.has(edge.dst)) next.add(edge.src);
    });
    next.forEach((id) => included.add(id));
    frontier = next;
  }

  const nodes = state.data.nodes.filter((node) => included.has(node.id));
  const edges = state.data.edges.filter(
    (edge) => included.has(edge.src) && included.has(edge.dst),
  );
  return { nodes, edges };
}

function formatNumber(value) {
  return new Intl.NumberFormat("ko-KR").format(Math.round(value));
}

function percentChange(current, previous) {
  if (!previous) return null;
  return ((current - previous) / previous) * 100;
}

function changeLabel(change) {
  if (change === null || Number.isNaN(change)) return "이전 비교 없음";
  const sign = change > 0 ? "+" : "";
  return `이전 기간보다 ${sign}${change.toFixed(1)}%`;
}

function statusClass(status) {
  if (status === "우선 확인") return "status-review";
  if (status === "관찰") return "status-watch";
  return "status-normal";
}

function renderSearchResults() {
  const query = state.query.trim().toLocaleLowerCase("ko");
  const matches = state.data.nodes.filter(
    (node) => !query || node.name.toLocaleLowerCase("ko").includes(query),
  );
  elements.entitySelect.replaceChildren();
  matches.slice(0, 50).forEach((node) => {
    const option = document.createElement("option");
    option.value = node.id;
    option.textContent = `${node.name} · ${node.type}`;
    elements.entitySelect.append(option);
  });
  elements.searchCount.textContent = `${matches.length}개 업체를 찾았습니다.`;

  if (matches.length && !matches.some((node) => node.id === state.focalId)) {
    state.focalId = matches[0].id;
  }
  elements.entitySelect.value = state.focalId;
}

function renderAnchors() {
  elements.anchor.replaceChildren();
  state.data.meta.anchors.forEach((anchor) => {
    const option = document.createElement("option");
    option.value = anchor.value;
    option.textContent = anchor.label;
    elements.anchor.append(option);
  });
  elements.anchor.value = state.anchor;
}

function renderConclusion() {
  const node = nodeMap().get(state.focalId);
  const edges = incidentEdges();
  const current = edges.reduce(
    (total, edge) => total + aggregateEdge(edge).count,
    0,
  );
  const previous = edges.reduce(
    (total, edge) => total + aggregateEdge(edge, previousMonths()).count,
    0,
  );
  const countChange = percentChange(current, previous);
  const reviewCount = state.data.reviewOrder.filter((id) => {
    const candidate = nodeMap().get(id);
    return candidate && candidate.status !== "정상";
  }).length;

  elements.conclusionHeadline.textContent =
    `${node.name}은(는) ${node.type}으로, ${node.status} 상태입니다`;
  elements.conclusionBody.innerHTML =
    `<span class="conclusion-line"><strong>위치:</strong> ${selectedMonths()[0]}~${selectedMonths().at(-1)} 기준 ${state.depth}단계 연결망에 있습니다.</span>` +
    `<span class="conclusion-line"><strong>변화:</strong> 거래 보고는 ${changeLabel(countChange)}.</span>` +
    `<span class="conclusion-line"><strong>확인:</strong> 우선 살펴볼 업체 ${reviewCount}곳이 있습니다. ${node.reviewQuestion}</span>`;
}

function updateFlowSteps() {
  if (!elements.flowSteps) return;
  const sections = [
    { id: "orient", el: elements.sectionOrient },
    { id: "change", el: elements.sectionChange },
    { id: "check", el: elements.sectionCheck },
  ];
  const stickyOffset = elements.flowSteps.getBoundingClientRect().height + 12;
  const viewportMid = stickyOffset + window.innerHeight * 0.22;
  let active = "orient";
  sections.forEach((section) => {
    if (!section.el) return;
    const rect = section.el.getBoundingClientRect();
    if (rect.top <= viewportMid) active = section.id;
  });
  elements.flowSteps.querySelectorAll(".flow-step").forEach((step) => {
    const stepId = step.dataset.step;
    step.classList.remove("flow-step--current", "flow-step--done");
    step.removeAttribute("aria-current");
    const order = ["orient", "change", "check"];
    const activeIndex = order.indexOf(active);
    const stepIndex = order.indexOf(stepId);
    if (stepIndex === activeIndex) {
      step.classList.add("flow-step--current");
      step.setAttribute("aria-current", "step");
    } else if (stepIndex < activeIndex) {
      step.classList.add("flow-step--done");
    }
  });
}

function scrollToStep(targetId) {
  const target = document.getElementById(targetId);
  if (!target) return;
  const stickyHeight = elements.flowSteps?.getBoundingClientRect().height || 0;
  const top = window.scrollY + target.getBoundingClientRect().top - stickyHeight - 12;
  window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
}

function renderMetrics() {
  const nodes = nodeMap();
  const edges = incidentEdges();
  const inbound = new Set(edges.filter((edge) => edge.dst === state.focalId).map((edge) => edge.src));
  const outbound = new Set(edges.filter((edge) => edge.src === state.focalId).map((edge) => edge.dst));
  const current = edges.reduce(
    (total, edge) => {
      const aggregate = aggregateEdge(edge);
      total.count += aggregate.count;
      total.quantity += aggregate.quantity;
      return total;
    },
    { count: 0, quantity: 0 },
  );
  const previous = edges.reduce(
    (total, edge) => {
      const aggregate = aggregateEdge(edge, previousMonths());
      total.count += aggregate.count;
      total.quantity += aggregate.quantity;
      return total;
    },
    { count: 0, quantity: 0 },
  );
  const countChange = percentChange(current.count, previous.count);
  const focal = nodes.get(state.focalId);

  const cards = [
    ["공급해 온 업체", `${inbound.size}개`, "현재 선택 업체로 들어오는 연결"],
    ["공급받은 기관", `${outbound.size}개`, "현재 선택 업체에서 나가는 연결"],
    ["거래 보고 횟수", `${formatNumber(current.count)}건`, changeLabel(countChange)],
    ["공급 수량", `${formatNumber(current.quantity)}개`, "포장 단위 기반 예시 합계"],
  ];

  elements.metrics.innerHTML = cards
    .map(
      ([label, value, note]) => `
        <article class="metric">
          <p class="metric-label">${label}</p>
          <p class="metric-value">${value}</p>
          <p class="metric-note">${note}</p>
        </article>
      `,
    )
    .join("");
  elements.selectionDescription.textContent =
    `${focal.name} · ${selectedMonths()[0]}~${selectedMonths().at(-1)} · ${state.depth}단계 연결`;
}

function graphLane(node) {
  return ["제조사", "수입사"].includes(node.type) ? "공급원" : node.type;
}

function nodeRadius(node) {
  return 10 + Math.min(16, Math.sqrt(node.degree) * 3);
}

function estimateLabelWidth(text) {
  let width = 0;
  for (const char of text) {
    width += /[A-Za-z0-9 .·-]/.test(char) ? LABEL_FONT_SIZE * 0.58 : LABEL_FONT_SIZE;
  }
  return Math.ceil(width);
}

function shortenLabel(name, maxChars) {
  if (name.length <= maxChars) return name;
  return `${name.slice(0, Math.max(1, maxChars - 1))}…`;
}

function graphPositions(nodes) {
  const grouped = new Map();
  nodes.forEach((node) => {
    const lane = graphLane(node);
    if (!grouped.has(lane)) grouped.set(lane, []);
    grouped.get(lane).push(node);
  });

  const minGap = 52;
  const laneCounts = [...grouped.values()].map((items) => items.length);
  const maxCount = Math.max(...laneCounts, 1);
  const graphHeight = Math.max(560, maxCount * minGap + 100);

  const positions = new Map();
  grouped.forEach((items, lane) => {
    const sorted = [...items].sort((a, b) => a.name.localeCompare(b.name, "ko"));
    const laneHeight = Math.max(graphHeight - 90, sorted.length * minGap);
    const step = laneHeight / Math.max(sorted.length, 1);
    sorted.forEach((node, index) => {
      positions.set(node.id, {
        x: X_BY_LANE[lane] || 490,
        y: 48 + step * index + step / 2,
        lane,
        laneIndex: index,
        laneCount: sorted.length,
        graphHeight,
      });
    });
  });
  return positions;
}

function labelSideFor(lane, laneIndex) {
  if (lane === "공급원") return "left";
  if (lane === "의료기관") return "right";
  return laneIndex % 2 === 0 ? "left" : "right";
}

function buildLabelLayout(nodes, positions) {
  const dense = nodes.length > 18;
  const candidates = nodes.map((node) => {
    const position = positions.get(node.id);
    const radius = nodeRadius(node);
    const selected = node.id === state.focalId;
    const maxChars = selected ? 14 : dense ? 7 : 10;
    const displayName = shortenLabel(node.name, maxChars);
    const side = labelSideFor(position.lane, position.laneIndex);
    const width = estimateLabelWidth(displayName);
    const x =
      side === "left"
        ? position.x - radius - LABEL_PAD
        : position.x + radius + LABEL_PAD;
    const y = position.y + 4;
    return {
      id: node.id,
      name: node.name,
      displayName,
      selected,
      side,
      x,
      y,
      width,
      height: LABEL_LINE_HEIGHT,
      top: y - LABEL_LINE_HEIGHT * 0.7,
      bottom: y + LABEL_LINE_HEIGHT * 0.45,
      left: side === "left" ? x - width : x,
      right: side === "left" ? x : x + width,
    };
  });

  const byLane = new Map();
  candidates.forEach((label) => {
    const lane = positions.get(label.id).lane;
    if (!byLane.has(lane)) byLane.set(lane, []);
    byLane.get(lane).push(label);
  });

  byLane.forEach((labels) => {
    labels.sort((a, b) => a.y - b.y);
    for (let i = 1; i < labels.length; i += 1) {
      const prev = labels[i - 1];
      const current = labels[i];
      const sameSide = prev.side === current.side;
      const horizontalOverlap =
        current.left < prev.right + 4 && current.right > prev.left - 4;
      if (sameSide && horizontalOverlap && current.top < prev.bottom + 4) {
        const shift = prev.bottom + 4 - current.top;
        current.y += shift;
        current.top += shift;
        current.bottom += shift;
      }
    }
  });

  return new Map(candidates.map((label) => [label.id, label]));
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function selectNode(nodeId) {
  state.focalId = nodeId;
  const node = nodeMap().get(nodeId);
  state.query = node.name;
  elements.search.value = node.name;
  renderSearchResults();
  renderAll();
}

function renderNetwork() {
  const graph = subgraph();
  const positions = graphPositions(graph.nodes);
  const labels = buildLabelLayout(graph.nodes, positions);
  const graphHeight = Math.max(
    [...positions.values()][0]?.graphHeight || 560,
    ...[...labels.values()].map((label) => label.bottom + 28),
  );
  elements.svg.setAttribute("viewBox", `0 0 ${GRAPH_WIDTH} ${graphHeight}`);
  elements.svg.style.height = `${graphHeight}px`;

  const maxMeasure = Math.max(
    ...graph.edges.map((edge) => aggregateEdge(edge)[state.edgeMeasure]),
    1,
  );

  elements.svg.replaceChildren();
  const defs = svgElement("defs");
  const marker = svgElement("marker", {
    id: "arrow",
    viewBox: "0 0 10 10",
    refX: 9,
    refY: 5,
    markerWidth: 7,
    markerHeight: 7,
    orient: "auto-start-reverse",
  });
  marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#718096" }));
  defs.append(marker);
  elements.svg.append(defs);

  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const edgeLayer = svgElement("g", { "aria-hidden": "true" });
  graph.edges.forEach((edge) => {
    const source = positions.get(edge.src);
    const target = positions.get(edge.dst);
    if (!source || !target) return;
    const sourceNode = nodeById.get(edge.src);
    const targetNode = nodeById.get(edge.dst);
    const srcRadius = nodeRadius(sourceNode);
    const dstRadius = nodeRadius(targetNode);
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const distance = Math.hypot(dx, dy) || 1;
    const measure = aggregateEdge(edge)[state.edgeMeasure];
    const width = 1.2 + Math.sqrt(measure / maxMeasure) * 6;
    edgeLayer.append(
      svgElement("line", {
        x1: source.x + (dx / distance) * srcRadius,
        y1: source.y + (dy / distance) * srcRadius,
        x2: target.x - (dx / distance) * (dstRadius + 6),
        y2: target.y - (dy / distance) * (dstRadius + 6),
        stroke: "#91a0af",
        "stroke-width": width.toFixed(1),
        "stroke-opacity": 0.72,
        "marker-end": "url(#arrow)",
      }),
    );
  });
  elements.svg.append(edgeLayer);

  const nodeLayer = svgElement("g");
  graph.nodes.forEach((node) => {
    const position = positions.get(node.id);
    const labelInfo = labels.get(node.id);
    const group = svgElement("g", {
      role: "button",
      tabindex: "0",
      "aria-label": `${node.name}, ${node.type}, 관계 AI 점수 ${gnnScore(node)}`,
      style: "cursor:pointer",
    });
    const radius = nodeRadius(node);
    const selected = node.id === state.focalId;
    const circle = svgElement("circle", {
      cx: position.x,
      cy: position.y,
      r: radius,
      fill: COLORS[node.type] || "#667085",
      stroke: selected ? "#12345b" : node.status === "우선 확인" ? "#a51d2d" : "#ffffff",
      "stroke-width": selected ? 5 : node.status === "우선 확인" ? 4 : 2,
    });
    const label = svgElement("text", {
      x: labelInfo.x,
      y: labelInfo.y,
      "text-anchor": labelInfo.side === "left" ? "end" : "start",
      fill: "#17212b",
      "font-size": LABEL_FONT_SIZE,
      "font-weight": selected ? 800 : 650,
      class: selected ? "entity-label entity-label--focal" : "entity-label",
    });
    if (labelInfo.displayName !== node.name) {
      const title = svgElement("title");
      title.textContent = node.name;
      label.append(title);
    }
    label.append(document.createTextNode(labelInfo.displayName));
    group.append(circle, label);
    group.addEventListener("click", () => selectNode(node.id));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(node.id);
      }
    });
    nodeLayer.append(group);
  });
  elements.svg.append(nodeLayer);

  elements.graphDescription.textContent =
    `${graph.nodes.length}개 기관 · ${graph.edges.length}개 연결 · 선 굵기: ${
      state.edgeMeasure === "count" ? "거래 보고 횟수" : "공급 수량"
    }`;
}

function renderDetail() {
  const node = nodeMap().get(state.focalId);
  const score = gnnScore(node);
  elements.detail.innerHTML = `
    <p class="eyebrow">선택 업체</p>
    <h4>${node.name}</h4>
    <p><span class="status ${statusClass(node.status)}">${node.status}</span></p>
    <ul class="detail-list">
      <li><span>업체 구분</span><strong>${node.type}</strong></li>
      <li><span>전체 연결 수</span><strong>${node.degree}개</strong></li>
      <li><span>관계 AI 점수</span><strong>${score} / 100</strong></li>
    </ul>
    <p class="field-help">관계 AI 점수만으로 순위를 매깁니다. 속성별 기여 문장은 제공되지 않습니다.</p>
  `;
}

function relationshipRow(row) {
  return `
    <tr>
      <td><strong>${row.connected.name}</strong></td>
      <td>${row.connected.type}</td>
      <td>${formatNumber(row.count)}건</td>
      <td>${formatNumber(row.quantity)}개</td>
      <td>${row.item}</td>
    </tr>
  `;
}

function renderRelationships() {
  const nodes = nodeMap();
  const inbound = [];
  const outbound = [];
  incidentEdges().forEach((edge) => {
    const isOutbound = edge.src === state.focalId;
    const connected = nodes.get(isOutbound ? edge.dst : edge.src);
    const row = { connected, item: edge.item, ...aggregateEdge(edge) };
    if (isOutbound) outbound.push(row);
    else inbound.push(row);
  });
  const sortKey = state.edgeMeasure;
  inbound.sort((a, b) => b[sortKey] - a[sortKey]);
  outbound.sort((a, b) => b[sortKey] - a[sortKey]);

  elements.inboundBody.innerHTML = inbound.length
    ? inbound.map(relationshipRow).join("")
    : `<tr><td colspan="5">공급받은 연결이 없습니다.</td></tr>`;
  elements.outboundBody.innerHTML = outbound.length
    ? outbound.map(relationshipRow).join("")
    : `<tr><td colspan="5">공급한 연결이 없습니다.</td></tr>`;
}

function renderReviewTable() {
  const nodes = nodeMap();
  const reviewNodes = state.data.reviewOrder.slice(0, 10).map((id) => nodes.get(id));
  elements.reviewBody.innerHTML = reviewNodes
    .map((node) => `
        <tr class="clickable-row" data-entity-id="${node.id}" tabindex="0">
          <td><strong>${node.name}</strong></td>
          <td>${gnnScore(node)}점</td>
          <td><span class="status ${statusClass(node.status)}">${node.status}</span></td>
        </tr>
      `)
    .join("");

  elements.reviewBody.querySelectorAll("tr").forEach((row) => {
    const open = () => selectNode(row.dataset.entityId);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

function renderEvidence() {
  const node = nodeMap().get(state.focalId);
  elements.evidenceGrid.innerHTML = `
    <article class="evidence evidence-fact">
      <h4>1. 관찰된 사실</h4>
      <p>${node.observedFact}</p>
    </article>
    <article class="evidence evidence-model">
      <h4>2. 관계 구조 AI 해석</h4>
      <p>${node.modelInterpretation}</p>
    </article>
    <article class="evidence evidence-question">
      <h4>3. 확인할 질문</h4>
      <p>${node.reviewQuestion}</p>
    </article>
  `;
}

function renderAll() {
  renderConclusion();
  renderMetrics();
  renderNetwork();
  renderDetail();
  renderRelationships();
  renderReviewTable();
  renderEvidence();
  updateFlowSteps();
}

function bindEvents() {
  elements.search.addEventListener("input", (event) => {
    state.query = event.target.value;
    renderSearchResults();
    renderAll();
  });
  elements.entitySelect.addEventListener("change", (event) => {
    state.focalId = event.target.value;
    renderAll();
  });
  elements.anchor.addEventListener("change", (event) => {
    state.anchor = event.target.value;
    renderAll();
  });
  elements.depthButtons.forEach((button) => {
    button.addEventListener("click", () => {
      state.depth = Number(button.dataset.depth);
      elements.depthButtons.forEach((candidate) => {
        candidate.setAttribute("aria-pressed", String(candidate === button));
      });
      renderAll();
    });
  });
  elements.edgeMeasure.addEventListener("change", (event) => {
    state.edgeMeasure = event.target.value;
    renderAll();
  });
  elements.showMyCompanyButton.addEventListener("click", () => {
    selectNode(myCompanyId());
  });
  const myCompanyLabel = state.data.meta.myCompanyName;
  if (myCompanyLabel) {
    elements.showMyCompanyButton.textContent = `내 업체 보기 (${myCompanyLabel})`;
  }
  elements.flowSteps?.querySelectorAll(".flow-step").forEach((step) => {
    step.addEventListener("click", () => {
      scrollToStep(step.dataset.target);
      window.setTimeout(updateFlowSteps, 320);
    });
  });
  window.addEventListener("scroll", updateFlowSteps, { passive: true });
  window.addEventListener("resize", updateFlowSteps, { passive: true });
}

async function init() {
  const response = await fetch("./data/mock_data.json");
  if (!response.ok) throw new Error("Class 1 mock data could not be loaded.");
  state.data = await response.json();
  renderAnchors();
  renderSearchResults();
  elements.limitationList.innerHTML = state.data.limitations
    .map((limitation) => `<li>${limitation}</li>`)
    .join("");
  bindEvents();
  renderAll();
}

init().catch((error) => {
  console.error(error);
  document.getElementById("main").innerHTML = `
    <section class="panel empty-message">
      <h2>예시 데이터를 불러오지 못했습니다.</h2>
      <p>저장소 루트에서 HTTP 서버를 실행했는지 확인해 주세요.</p>
    </section>
  `;
});
