const state = {
  data: null,
  focalId: "D03",
  query: "C 유통",
  anchor: "202605",
  depth: 0,
  edgeMeasure: "count",
  stage: "brief",
  labelMode: "review",
  highlightEdgeId: null,
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
const STAGE_ORDER = ["brief", "change", "graph", "packet"];
const X_BY_LANE = { 공급원: 150, 유통사: 490, 의료기관: 830 };

const elements = {
  search: document.getElementById("entitySearch"),
  entitySelect: document.getElementById("entitySelect"),
  searchCount: document.getElementById("searchCount"),
  anchor: document.getElementById("anchorMonth"),
  edgeMeasure: document.getElementById("edgeMeasure"),
  showMyCompanyButton: document.getElementById("showMyCompanyButton"),
  progressRail: document.getElementById("progressRail"),
  briefHeading: document.getElementById("brief-heading"),
  briefStatus: document.getElementById("briefStatus"),
  briefHeadline: document.getElementById("briefHeadline"),
  briefMetrics: document.getElementById("briefMetrics"),
  changeOverall: document.getElementById("changeOverall"),
  changeBoard: document.getElementById("changeBoard"),
  graphDescription: document.getElementById("graphDescription"),
  svg: document.getElementById("networkSvg"),
  detail: document.getElementById("entityDetail"),
  inboundBody: document.getElementById("inboundBody"),
  outboundBody: document.getElementById("outboundBody"),
  reviewCards: document.getElementById("reviewCards"),
  reviewBody: document.getElementById("reviewBody"),
  limitationList: document.getElementById("limitationList"),
  expandOneHop: document.getElementById("expandOneHop"),
  expandTwoHop: document.getElementById("expandTwoHop"),
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
  return state.data.meta.availableMonths.filter((month) => month <= anchor).slice(-3);
}

function previousMonths() {
  return state.data.meta.availableMonths.filter((month) => month < selectedMonths()[0]).slice(-3);
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
  if (depth <= 0) {
    return { nodes: state.data.nodes.filter((n) => included.has(n.id)), edges: [] };
  }
  let frontier = new Set([state.focalId]);
  for (let hop = 0; hop < depth; hop += 1) {
    const next = new Set();
    state.data.edges.forEach((edge) => {
      const current = aggregateEdge(edge);
      const previous = aggregateEdge(edge, previousMonths());
      if (current.count === 0 && previous.count === 0) return;
      if (frontier.has(edge.src)) next.add(edge.dst);
      if (frontier.has(edge.dst)) next.add(edge.src);
    });
    next.forEach((id) => included.add(id));
    frontier = next;
  }
  return {
    nodes: state.data.nodes.filter((node) => included.has(node.id)),
    edges: state.data.edges.filter((edge) => {
      if (!included.has(edge.src) || !included.has(edge.dst)) return false;
      const current = aggregateEdge(edge);
      const previous = aggregateEdge(edge, previousMonths());
      return current.count > 0 || previous.count > 0;
    }),
  };
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

function displayStatus(status) {
  return status === "일반" ? "정상" : status;
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function goStage(stage) {
  if (!STAGE_ORDER.includes(stage)) return;
  state.stage = stage;
  STAGE_ORDER.forEach((id) => {
    const panel = document.getElementById(`stage-${id}`);
    if (!panel) return;
    const active = id === stage;
    panel.hidden = !active;
    panel.classList.toggle("stage-enter", active && !prefersReducedMotion());
  });
  elements.progressRail.querySelectorAll("button").forEach((step) => {
    const stepId = step.dataset.stage;
    const orderIndex = STAGE_ORDER.indexOf(stepId);
    const activeIndex = STAGE_ORDER.indexOf(stage);
    step.removeAttribute("aria-current");
    step.classList.toggle("is-done", orderIndex < activeIndex);
    if (orderIndex === activeIndex) step.setAttribute("aria-current", "step");
  });
  renderStageContent();
  const activePanel = document.getElementById(`stage-${stage}`);
  if (activePanel) {
    const top = window.scrollY + activePanel.getBoundingClientRect().top - 80;
    window.scrollTo({ top: Math.max(0, top), behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }
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

function selectNode(nodeId, options = {}) {
  state.focalId = nodeId;
  const node = nodeMap().get(nodeId);
  state.query = node.name;
  elements.search.value = node.name;
  state.depth = options.resetDepth === false ? state.depth : 0;
  state.highlightEdgeId = options.highlightEdgeId || null;
  renderSearchResults();
  renderAll();
  if (options.stage) goStage(options.stage);
}

function renderBrief() {
  const nodes = nodeMap();
  const focal = nodes.get(state.focalId);
  const edges = incidentEdges();
  const inbound = new Set(
    edges.filter((e) => e.dst === state.focalId && aggregateEdge(e).count > 0).map((e) => e.src),
  );
  const outbound = new Set(
    edges.filter((e) => e.src === state.focalId && aggregateEdge(e).count > 0).map((e) => e.dst),
  );
  const current = edges.reduce(
    (t, e) => {
      const a = aggregateEdge(e);
      t.count += a.count;
      t.quantity += a.quantity;
      return t;
    },
    { count: 0, quantity: 0 },
  );
  const previous = edges.reduce(
    (t, e) => {
      const a = aggregateEdge(e, previousMonths());
      t.count += a.count;
      t.quantity += a.quantity;
      return t;
    },
    { count: 0, quantity: 0 },
  );
  const countChange = percentChange(current.count, previous.count);

  elements.briefHeading.textContent = `${focal.name}`;
  elements.briefStatus.textContent = displayStatus(focal.status);
  elements.briefStatus.className = `status ${statusClass(focal.status)}`;
  elements.briefHeadline.textContent = `${selectedMonths()[0]}~${selectedMonths().at(-1)}`;

  const cards = [
    ["공급해 온 업체", `${inbound.size}개`, "들어오는 연결"],
    ["공급받은 기관", `${outbound.size}개`, "나가는 연결"],
    ["거래 보고", `${formatNumber(current.count)}건`, changeLabel(countChange)],
    ["공급 수량", `${formatNumber(current.quantity)}개`, "예시 합계"],
  ];
  elements.briefMetrics.innerHTML = cards
    .map(
      ([label, value, note]) => `
      <article>
        <p class="metric-label">${label}</p>
        <p class="metric-value">${value}</p>
        <p class="metric-note">${note}</p>
      </article>`,
    )
    .join("");
}

function classifyEdgeChange(edge) {
  const current = aggregateEdge(edge);
  const previous = aggregateEdge(edge, previousMonths());
  const measure = state.edgeMeasure;
  const cur = current[measure];
  const prev = previous[measure];
  if (cur > 0 && prev === 0) return "new";
  if (cur === 0 && prev > 0) return "lost";
  if (prev > 0 && cur >= prev * 1.8) return "surging";
  return "stable";
}

function partnerForEdge(edge) {
  const nodes = nodeMap();
  const outbound = edge.src === state.focalId;
  return {
    partner: nodes.get(outbound ? edge.dst : edge.src),
    direction: outbound ? "공급함" : "공급받음",
    current: aggregateEdge(edge),
    previous: aggregateEdge(edge, previousMonths()),
  };
}

function renderChangeBoard() {
  const edges = incidentEdges();
  const currentTotal = edges.reduce((s, e) => s + aggregateEdge(e).count, 0);
  const previousTotal = edges.reduce((s, e) => s + aggregateEdge(e, previousMonths()).count, 0);
  elements.changeOverall.textContent =
    `기준 ${selectedMonths()[0]}~${selectedMonths().at(-1)} · 거래 보고 ${changeLabel(percentChange(currentTotal, previousTotal))}.`;

  const groups = { surging: [], new: [], lost: [] };
  edges.forEach((edge) => {
    const kind = classifyEdgeChange(edge);
    if (!groups[kind]) return;
    groups[kind].push({ edge, ...partnerForEdge(edge), kind });
  });
  const sortKey = state.edgeMeasure;
  groups.surging.sort((a, b) => b.current[sortKey] / Math.max(1, b.previous[sortKey]) - a.current[sortKey] / Math.max(1, a.previous[sortKey]));
  groups.new.sort((a, b) => b.current[sortKey] - a.current[sortKey]);
  groups.lost.sort((a, b) => b.previous[sortKey] - a.previous[sortKey]);

  const sections = [
    { key: "surging", title: "급증한 연결", className: "reel-col--surge", empty: "급증한 연결이 없습니다." },
    { key: "new", title: "새로 나타난 연결", className: "reel-col--new", empty: "이 기간에는 신규 연결이 없습니다." },
    { key: "lost", title: "끊긴 연결", className: "reel-col--lost", empty: "이 기간에는 단절 연결이 없습니다." },
  ];

  elements.changeBoard.innerHTML = sections
    .map((section) => {
      const rows = groups[section.key].slice(0, 5);
      const body = rows.length
        ? rows
            .map((row) => {
              const measure =
                section.key === "lost"
                  ? `이전 ${formatNumber(row.previous[sortKey])}${sortKey === "count" ? "건" : "개"}`
                  : `${formatNumber(row.current[sortKey])}${sortKey === "count" ? "건" : "개"}`;
              return `
                <button type="button" class="reel-item" data-highlight-edge="${row.edge.id}">
                  <strong>${row.partner.name}</strong>
                  <span>${row.direction} · ${row.partner.type} · ${measure}</span>
                </button>`;
            })
            .join("")
        : `<p class="reel-empty">${section.empty}</p>`;
      return `
        <section class="reel-col ${section.className}">
          <h3>${section.title} <span class="status status-normal">${rows.length}</span></h3>
          ${body}
        </section>`;
    })
    .join("");

  elements.changeBoard.querySelectorAll("[data-highlight-edge]").forEach((button) => {
    button.addEventListener("click", () => {
      state.highlightEdgeId = button.dataset.highlightEdge;
      state.depth = Math.max(state.depth, 1);
      goStage("graph");
    });
  });
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
  const maxCount = Math.max(...[...grouped.values()].map((i) => i.length), 1);
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
    const reviewNeeded = node.status === "우선 확인" || node.status === "관찰";
    const showFull = state.labelMode === "all" || selected || reviewNeeded;
    const maxChars = selected ? 14 : showFull ? (dense ? 7 : 10) : 0;
    const displayName = maxChars === 0 ? "" : shortenLabel(node.name, maxChars);
    const side = labelSideFor(position.lane, position.laneIndex);
    const width = displayName ? estimateLabelWidth(displayName) : 0;
    const x = side === "left" ? position.x - radius - LABEL_PAD : position.x + radius + LABEL_PAD;
    const y = position.y + 4;
    return {
      id: node.id,
      name: node.name,
      displayName,
      selected,
      side,
      x,
      y,
      top: y - LABEL_LINE_HEIGHT * 0.7,
      bottom: y + LABEL_LINE_HEIGHT * 0.45,
      left: side === "left" ? x - width : x,
      right: side === "left" ? x : x + width,
    };
  });
  const byLane = new Map();
  candidates.forEach((label) => {
    if (!label.displayName) return;
    const lane = positions.get(label.id).lane;
    if (!byLane.has(lane)) byLane.set(lane, []);
    byLane.get(lane).push(label);
  });
  byLane.forEach((labels) => {
    labels.sort((a, b) => a.y - b.y);
    for (let i = 1; i < labels.length; i += 1) {
      const prev = labels[i - 1];
      const current = labels[i];
      const overlap = current.left < prev.right + 4 && current.right > prev.left - 4;
      if (prev.side === current.side && overlap && current.top < prev.bottom + 4) {
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

function renderNetwork() {
  const graph = subgraph();
  const positions = graphPositions(graph.nodes);
  const labels = buildLabelLayout(graph.nodes, positions);
  const graphHeight = Math.max(
    [...positions.values()][0]?.graphHeight || 560,
    ...[...labels.values()].map((label) => (label.displayName ? label.bottom + 28 : 0)),
  );
  elements.svg.setAttribute("viewBox", `0 0 ${GRAPH_WIDTH} ${graphHeight}`);
  elements.svg.style.height = `${graphHeight}px`;
  elements.svg.replaceChildren();

  const maxMeasure = Math.max(
    ...graph.edges.map((edge) => aggregateEdge(edge)[state.edgeMeasure] || 0),
    1,
  );

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
    if (aggregateEdge(edge).count === 0 && edge.id !== state.highlightEdgeId) {
      if (aggregateEdge(edge, previousMonths()).count === 0) return;
    }
    const sourceNode = nodeById.get(edge.src);
    const targetNode = nodeById.get(edge.dst);
    const srcRadius = nodeRadius(sourceNode);
    const dstRadius = nodeRadius(targetNode);
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const distance = Math.hypot(dx, dy) || 1;
    const measure =
      aggregateEdge(edge)[state.edgeMeasure] ||
      aggregateEdge(edge, previousMonths())[state.edgeMeasure];
    const width = 1.2 + Math.sqrt(measure / maxMeasure) * 6;
    const highlighted = edge.id === state.highlightEdgeId;
    edgeLayer.append(
      svgElement("line", {
        x1: source.x + (dx / distance) * srcRadius,
        y1: source.y + (dy / distance) * srcRadius,
        x2: target.x - (dx / distance) * (dstRadius + 6),
        y2: target.y - (dy / distance) * (dstRadius + 6),
        stroke: highlighted ? "#a44800" : "#91a0af",
        "stroke-width": highlighted ? Math.max(width, 4).toFixed(1) : width.toFixed(1),
        "stroke-opacity": highlighted ? 1 : 0.72,
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
    group.append(
      svgElement("circle", {
        cx: position.x,
        cy: position.y,
        r: radius,
        fill: COLORS[node.type] || "#667085",
        stroke: selected ? "#12345b" : node.status === "우선 확인" ? "#a51d2d" : "#ffffff",
        "stroke-width": selected ? 5 : node.status === "우선 확인" ? 4 : 2,
      }),
    );
    if (labelInfo.displayName) {
      const label = svgElement("text", {
        x: labelInfo.x,
        y: labelInfo.y,
        "text-anchor": labelInfo.side === "left" ? "end" : "start",
        fill: "#17212b",
        "font-size": LABEL_FONT_SIZE,
        "font-weight": selected ? 800 : 650,
        class: "entity-label",
      });
      if (labelInfo.displayName !== node.name) {
        const title = svgElement("title");
        title.textContent = node.name;
        label.append(title);
      }
      label.append(document.createTextNode(labelInfo.displayName));
      group.append(label);
    }
    group.addEventListener("click", () => selectNode(node.id, { resetDepth: false, stage: "brief" }));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(node.id, { resetDepth: false, stage: "brief" });
      }
    });
    nodeLayer.append(group);
  });
  elements.svg.append(nodeLayer);

  elements.graphDescription.textContent =
    state.depth === 0
      ? "선택 업체만 표시 중입니다. 아래에서 연결을 펼쳐 보세요."
      : `${graph.nodes.length}개 기관 · ${graph.edges.length}개 연결 · ${state.depth}단계`;
  elements.expandOneHop.setAttribute("aria-pressed", String(state.depth >= 1));
  elements.expandTwoHop.setAttribute("aria-pressed", String(state.depth >= 2));
}

function renderDetail() {
  const node = nodeMap().get(state.focalId);
  elements.detail.innerHTML = `
    <p class="lab-eyebrow">선택 업체</p>
    <h3>${node.name}</h3>
    <p><span class="status ${statusClass(node.status)}">${displayStatus(node.status)}</span></p>
    <ul class="detail-list">
      <li><span>업체 구분</span><strong>${node.type}</strong></li>
      <li><span>전체 연결 수</span><strong>${node.degree}개</strong></li>
      <li><span>관계 AI 점수</span><strong>${gnnScore(node)} / 100</strong></li>
    </ul>`;
}

function relationshipRow(row) {
  return `<tr>
    <td><strong>${row.connected.name}</strong></td>
    <td>${row.connected.type}</td>
    <td>${formatNumber(row.count)}건</td>
    <td>${formatNumber(row.quantity)}개</td>
    <td>${row.item}</td>
  </tr>`;
}

function renderRelationships() {
  const nodes = nodeMap();
  const inbound = [];
  const outbound = [];
  incidentEdges().forEach((edge) => {
    if (aggregateEdge(edge).count === 0) return;
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

function renderReviewPacket() {
  const nodes = nodeMap();
  const reviewNodes = state.data.reviewOrder
    .slice(0, 10)
    .map((id) => nodes.get(id))
    .filter(Boolean);
  elements.reviewCards.innerHTML = reviewNodes
    .slice(0, 3)
    .map(
      (node, index) => `
      <article class="priority-board">
        <div class="priority-rank">${String(index + 1).padStart(2, "0")}</div>
        <div>
          <h3>${node.name}</h3>
          <div class="priority-meta">
            <span class="status ${statusClass(node.status)}">${displayStatus(node.status)}</span>
            <span class="status status-normal">관계 AI ${gnnScore(node)}점</span>
          </div>
          <div class="triad">
            <article><h4>관찰된 사실</h4><p>${node.observedFact}</p></article>
            <article><h4>관계 AI 해석</h4><p>${node.modelInterpretation.replace(/GNN 점수/g, "관계 AI 점수")}</p></article>
            <article><h4>확인할 질문</h4><p>${node.reviewQuestion}</p></article>
          </div>
          <button type="button" class="btn btn-primary" data-open-case="${node.id}">이 업체 케이스로 열기</button>
        </div>
      </article>`,
    )
    .join("");

  elements.reviewCards.querySelectorAll("[data-open-case]").forEach((button) => {
    button.addEventListener("click", () => selectNode(button.dataset.openCase, { stage: "brief" }));
  });

  elements.reviewBody.innerHTML = reviewNodes
    .map(
      (node) => `
      <tr class="clickable-row" data-entity-id="${node.id}" tabindex="0">
        <td><strong>${node.name}</strong></td>
        <td>${gnnScore(node)}점</td>
        <td><span class="status ${statusClass(node.status)}">${displayStatus(node.status)}</span></td>
      </tr>`,
    )
    .join("");

  elements.reviewBody.querySelectorAll("tr").forEach((row) => {
    const open = () => selectNode(row.dataset.entityId, { stage: "brief" });
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

function renderStageContent() {
  if (state.stage === "brief") renderBrief();
  if (state.stage === "change") renderChangeBoard();
  if (state.stage === "graph") {
    renderNetwork();
    renderDetail();
    renderRelationships();
  }
  if (state.stage === "packet") renderReviewPacket();
}

function renderAll() {
  renderBrief();
  renderChangeBoard();
  renderNetwork();
  renderDetail();
  renderRelationships();
  renderReviewPacket();
}

function bindEvents() {
  elements.search.addEventListener("input", (event) => {
    state.query = event.target.value;
    renderSearchResults();
    renderAll();
  });
  elements.entitySelect.addEventListener("change", (event) => {
    selectNode(event.target.value, { stage: "brief" });
  });
  elements.anchor.addEventListener("change", (event) => {
    state.anchor = event.target.value;
    renderAll();
  });
  elements.edgeMeasure.addEventListener("change", (event) => {
    state.edgeMeasure = event.target.value;
    renderAll();
  });
  elements.showMyCompanyButton.addEventListener("click", () => {
    selectNode(myCompanyId(), { stage: "brief" });
  });
  elements.expandOneHop.addEventListener("click", () => {
    state.depth = state.depth >= 1 ? 0 : 1;
    renderNetwork();
  });
  elements.expandTwoHop.addEventListener("click", () => {
    state.depth = state.depth >= 2 ? 1 : 2;
    renderNetwork();
  });
  document.querySelectorAll("[data-label-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.labelMode = button.dataset.labelMode;
      document.querySelectorAll("[data-label-mode]").forEach((candidate) => {
        candidate.setAttribute("aria-pressed", String(candidate === button));
      });
      renderNetwork();
    });
  });
  document.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => goStage(button.dataset.go));
  });
  elements.progressRail.querySelectorAll("button").forEach((step) => {
    step.addEventListener("click", () => goStage(step.dataset.stage));
  });
}

async function init() {
  const response = await fetch("../class_1/data/mock_data.json");
  if (!response.ok) throw new Error("Class 1 mock data could not be loaded.");
  state.data = await response.json();
  const myCompanyLabel = state.data.meta.myCompanyName;
  if (myCompanyLabel) {
    elements.showMyCompanyButton.textContent = `내 업체 보기 (${myCompanyLabel})`;
  }
  elements.limitationList.innerHTML = state.data.limitations
    .map((limitation) => `<li>${limitation}</li>`)
    .join("");
  renderAnchors();
  renderSearchResults();
  bindEvents();
  renderAll();
  goStage("brief");
}

init().catch((error) => {
  console.error(error);
  document.getElementById("main").innerHTML = `
    <section class="panel">
      <h2 class="title">예시 데이터를 불러오지 못했습니다.</h2>
      <p class="lead">저장소 루트에서 HTTP 서버를 실행했는지 확인해 주세요.</p>
    </section>`;
});
