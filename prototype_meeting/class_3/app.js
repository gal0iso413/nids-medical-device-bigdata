const state = {
  data: null,
  profile: {
    businessType: "판매·임대업체",
    region: "수도권",
    productGroup: "B2. 임상화학검사기기",
  },
  profileApplied: false,
};

const elements = {
  businessType: document.getElementById("businessType"),
  region: document.getElementById("region"),
  productGroup: document.getElementById("productGroup"),
  applyProfile: document.getElementById("applyProfile"),
  profileSteps: document.getElementById("profileSteps"),
  conclusionHeadline: document.getElementById("conclusionHeadline"),
  conclusionBody: document.getElementById("conclusionBody"),
  flowSteps: document.getElementById("flowSteps"),
  cohortSummary: document.getElementById("cohortSummary"),
  resultPanel: document.getElementById("resultPanel"),
  cohortMetrics: document.getElementById("cohortMetrics"),
  trendChart: document.getElementById("trendChart"),
  opportunityChart: document.getElementById("opportunityChart"),
  opportunityTable: document.getElementById("opportunityTable"),
  similarGroups: document.getElementById("similarGroups"),
  reviewQuestions: document.getElementById("reviewQuestions"),
  privacyMessage: document.getElementById("privacyMessage"),
  hiddenFieldList: document.getElementById("hiddenFieldList"),
  limitationList: document.getElementById("limitationList"),
  tabs: [...document.querySelectorAll('[role="tab"]')],
  panels: [...document.querySelectorAll('[role="tabpanel"]')],
};

function scenario() {
  return state.data.scenarios[state.profile.businessType];
}

function fillOptions(select, options, selected) {
  select.replaceChildren();
  options.forEach((label) => {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    option.selected = label === selected;
    select.append(option);
  });
}

function fillProductOptions(select, taxonomy, selected) {
  select.replaceChildren();
  taxonomy.forEach((group) => {
    const optgroup = document.createElement("optgroup");
    optgroup.label = group.group;
    group.items.forEach((label) => {
      const option = document.createElement("option");
      option.value = label;
      option.textContent = label;
      option.selected = label === selected;
      optgroup.append(option);
    });
    select.append(optgroup);
  });
}

function profileIndices() {
  const options = state.data.profileOptions;
  return {
    region: options.regions.indexOf(state.profile.region),
    product: options.productGroups.indexOf(state.profile.productGroup),
  };
}

function cohortCount() {
  const indices = profileIndices();
  const regionFactor = 1 - indices.region * 0.055;
  const productFactor = 1 - (indices.product % 3) * 0.03;
  return Math.max(
    state.data.privacy.cohortFloor,
    Math.round(scenario().baseCohortCount * regionFactor * productFactor),
  );
}

function cohortCountDisplay() {
  const count = cohortCount();
  const step = count < 30 ? 5 : 10;
  const lower = Math.floor(count / step) * step;
  return `${Math.max(state.data.privacy.cohortFloor, lower)}~${lower + step - 1}개`;
}

function isSuppressedProfile() {
  return state.profile.businessType === "기타 관련기관" && state.profile.region === "제주권";
}

function positionClass(position) {
  if (position.includes("상위")) return "positive";
  if (position.includes("하위")) return "caution";
  return "";
}

function displayMetricValue(metric) {
  if (metric.label === "거래 활동 변화") {
    return growthBand(Number.parseFloat(metric.value));
  }
  if (metric.label === "취급 품목 폭") {
    const value = Number.parseInt(metric.value, 10);
    return `${Math.max(1, value - 1)}~${value + 1}개 군`;
  }
  if (metric.label === "거래처 유형 폭") {
    const value = Number.parseInt(metric.value, 10);
    return `${Math.max(1, value - 1)}~${value + 1}개 유형`;
  }
  return metric.value;
}

function renderConclusion() {
  if (isSuppressedProfile()) {
    elements.conclusionHeadline.textContent = "선택 조건의 비교군을 표시할 수 없습니다";
    elements.conclusionBody.textContent =
      "기업·기관 수가 공개 기준보다 적은 예시입니다. 권역을 넓히거나 업태 조건을 완화해 주세요.";
    return;
  }

  const metrics = scenario().metrics;
  const activity = metrics.find((metric) => metric.label === "거래 활동 변화") || metrics[0];
  const breadth = metrics.find((metric) => metric.label === "취급 품목 폭") || metrics[1];

  elements.conclusionHeadline.textContent =
    `${state.profile.region} ${state.profile.businessType} 기준, 거래 활동은 ${activity.position}에 해당합니다`;
  elements.conclusionBody.innerHTML =
    `<strong>위치:</strong> ${state.profile.productGroup} 관심 기업군 ${cohortCountDisplay()} 규모. ` +
    `<strong>변화:</strong> 거래 활동 ${displayMetricValue(activity)} (${activity.position}). ` +
    `<strong>확인:</strong> 취급 품목 폭은 ${displayMetricValue(breadth)} 수준입니다. 아래 「확인할 사항」 탭에서 질문을 확인하세요.`;
}

function updateProfileSteps() {
  if (!elements.profileSteps) return;
  const items = [...elements.profileSteps.querySelectorAll("li")];
  const focusMap = {
    businessType: 0,
    region: 1,
    productGroup: 2,
  };
  const activeId = document.activeElement?.id;
  let activeIndex = focusMap[activeId] ?? (state.profileApplied ? 3 : 2);

  items.forEach((item, index) => {
    item.classList.toggle("active", !state.profileApplied && index === activeIndex);
    item.classList.toggle("done", state.profileApplied || index < activeIndex);
  });

  elements.applyProfile.disabled = !(
    elements.businessType.value &&
    elements.region.value &&
    elements.productGroup.value
  );
}

function updateFlowSteps() {
  if (!elements.flowSteps) return;
  const activeTab = elements.tabs.find((tab) => tab.getAttribute("aria-selected") === "true");
  const tabId = activeTab?.id || "tab-overview";
  let active = "orient";
  if (tabId === "tab-questions") active = "check";
  else if (state.profileApplied) {
    const resultTop = elements.resultPanel?.getBoundingClientRect().top ?? 9999;
    active = resultTop < window.innerHeight * 0.45 ? "change" : "orient";
  }

  elements.flowSteps.querySelectorAll(".flow-step").forEach((step) => {
    const stepId = step.dataset.step;
    step.classList.remove("flow-step--current", "flow-step--done");
    const order = ["orient", "change", "check"];
    const activeIndex = order.indexOf(active);
    const stepIndex = order.indexOf(stepId);
    if (stepIndex === activeIndex) step.classList.add("flow-step--current");
    else if (stepIndex < activeIndex) step.classList.add("flow-step--done");
  });
}

function renderSummary() {
  if (isSuppressedProfile()) {
    elements.cohortSummary.innerHTML = `
      <p class="eyebrow">비교 결과 보호</p>
      <h3>선택 조건의 비교군을 표시할 수 없습니다</h3>
      <p>
        해당 조건은 기업·기관 수가 공개 기준보다 적은 예시입니다.
        권역을 넓히거나 업태 조건을 완화해 주세요.
      </p>
    `;
    return;
  }
  elements.cohortSummary.innerHTML = `
    <p class="eyebrow">현재 비교 기준</p>
    <h3>${state.profile.region} · ${state.profile.businessType}</h3>
    <p>
      <strong>${state.profile.productGroup}</strong>에 관심이 있는
      <strong>${cohortCountDisplay()} 기업·기관 규모</strong>의 생성 예시 집계입니다.
      개별 업체의 값이나 순위는 표시하지 않습니다.
    </p>
  `;
}

function renderMetrics() {
  elements.cohortMetrics.innerHTML = scenario().metrics
    .map(
      (metric) => `
        <article class="metric">
          <p class="metric-label">${metric.label}</p>
          <p class="metric-value">${displayMetricValue(metric)}</p>
          <p class="metric-note ${positionClass(metric.position)}">${metric.position}</p>
          <p class="metric-note">${metric.definition}</p>
        </article>
      `,
    )
    .join("");
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function textElement(text, attributes = {}) {
  const element = svgElement("text", attributes);
  element.textContent = text;
  return element;
}

function renderTrendChart() {
  const svg = elements.trendChart;
  const data = scenario().transactionSeries;
  const width = 900;
  const height = 380;
  const margin = { top: 32, right: 25, bottom: 52, left: 72 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const allValues = data.flatMap((row) => [row.profileAverage, row.peerMedian]);
  const min = Math.floor(Math.min(...allValues) * 0.88);
  const max = Math.ceil(Math.max(...allValues) * 1.08);
  const x = (index) => margin.left + (index / (data.length - 1)) * plotWidth;
  const y = (value) => margin.top + ((max - value) / (max - min || 1)) * plotHeight;
  const pathFor = (key) =>
    data.map((row, index) => `${index ? "L" : "M"} ${x(index)} ${y(row[key])}`).join(" ");

  svg.replaceChildren();
  for (let tick = 0; tick <= 4; tick += 1) {
    const value = min + ((max - min) * tick) / 4;
    const yPos = y(value);
    svg.append(
      svgElement("line", {
        x1: margin.left,
        y1: yPos,
        x2: width - margin.right,
        y2: yPos,
        stroke: "#d7e0e8",
        "stroke-width": 1,
      }),
      textElement(new Intl.NumberFormat("ko-KR", { notation: "compact" }).format(value), {
        x: margin.left - 10,
        y: yPos + 4,
        "text-anchor": "end",
        fill: "#536273",
        "font-size": 12,
      }),
    );
  }

  data.forEach((row, index) => {
    svg.append(
      textElement(row.month.slice(2), {
        x: x(index),
        y: height - 22,
        "text-anchor": "middle",
        fill: "#536273",
        "font-size": 12,
      }),
    );
  });

  svg.append(
    svgElement("path", {
      d: pathFor("profileAverage"),
      fill: "none",
      stroke: "#087f78",
      "stroke-width": 4,
    }),
    svgElement("path", {
      d: pathFor("peerMedian"),
      fill: "none",
      stroke: "#718096",
      "stroke-width": 3,
      "stroke-dasharray": "7 5",
    }),
  );

  data.forEach((row, index) => {
    svg.append(
      svgElement("circle", {
        cx: x(index),
        cy: y(row.profileAverage),
        r: 5,
        fill: "#087f78",
      }),
      svgElement("circle", {
        cx: x(index),
        cy: y(row.peerMedian),
        r: 4,
        fill: "#ffffff",
        stroke: "#718096",
        "stroke-width": 2,
      }),
    );
  });

  svg.append(
    svgElement("line", { x1: 500, y1: 18, x2: 530, y2: 18, stroke: "#087f78", "stroke-width": 4 }),
    textElement("내가 고른 조건 평균", { x: 537, y: 22, fill: "#293a4c", "font-size": 12 }),
    svgElement("line", {
      x1: 660,
      y1: 18,
      x2: 690,
      y2: 18,
      stroke: "#718096",
      "stroke-width": 3,
      "stroke-dasharray": "7 5",
    }),
    textElement("같은 업태·권역 중앙값", { x: 697, y: 22, fill: "#293a4c", "font-size": 12 }),
    textElement("거래 보고 건수", {
      x: 16,
      y: 18,
      fill: "#536273",
      "font-size": 12,
    }),
  );
}

function opportunityInterpretation(record) {
  const growth = record.growthPct >= 0 ? "증가" : "감소";
  const concentration =
    record.hhi > 0.25 ? "집중도가 높음" : record.hhi > 0.15 ? "집중도 보통" : "공급자 다양";
  return `${growth} · ${concentration}`;
}

function concentrationBand(hhi) {
  if (hhi > 0.25) return "높음";
  if (hhi > 0.15) return "보통";
  return "낮음";
}

function supplierCountBand(count) {
  const lower = Math.floor(count / 10) * 10;
  return `${Math.max(1, lower)}~${lower + 9}개`;
}

function growthBand(value) {
  const direction = value >= 0 ? "증가" : "감소";
  const absolute = Math.abs(value);
  const lower = Math.floor(absolute / 5) * 5;
  return `${lower}~${lower + 5}% ${direction}`;
}

function shareBand(value) {
  const lower = Math.floor(value / 5) * 5;
  return `${lower}~${lower + 5}%`;
}

function renderOpportunityChart() {
  const svg = elements.opportunityChart;
  const data = scenario().opportunities;
  const width = 760;
  const height = 430;
  const margin = { top: 42, right: 34, bottom: 68, left: 76 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const xMin = -12;
  const xMax = 32;
  const yMin = 0;
  const yMax = 0.5;
  const x = (value) => margin.left + ((value - xMin) / (xMax - xMin)) * plotWidth;
  const y = (value) => margin.top + ((yMax - value) / (yMax - yMin)) * plotHeight;

  svg.replaceChildren();
  [0, 10, 20, 30].forEach((tick) => {
    svg.append(
      svgElement("line", {
        x1: x(tick),
        y1: margin.top,
        x2: x(tick),
        y2: height - margin.bottom,
        stroke: tick === 0 ? "#8da0b3" : "#d7e0e8",
      }),
      textElement(`${tick}%`, {
        x: x(tick),
        y: height - 42,
        "text-anchor": "middle",
        fill: "#536273",
        "font-size": 12,
      }),
    );
  });
  [
    { value: 0.1, label: "낮음" },
    { value: 0.25, label: "보통" },
    { value: 0.4, label: "높음" },
  ].forEach((tick) => {
    svg.append(
      svgElement("line", {
        x1: margin.left,
        y1: y(tick.value),
        x2: width - margin.right,
        y2: y(tick.value),
        stroke: tick.value === 0.25 ? "#8da0b3" : "#d7e0e8",
        "stroke-dasharray": tick.value === 0.25 ? "6 4" : "",
      }),
      textElement(tick.label, {
        x: margin.left - 12,
        y: y(tick.value) + 4,
        "text-anchor": "end",
        fill: "#536273",
        "font-size": 12,
      }),
    );
  });

  svg.append(
    textElement("최근 거래 활동 증감률 (%)", {
      x: margin.left + plotWidth / 2,
      y: height - 10,
      "text-anchor": "middle",
      fill: "#293a4c",
      "font-size": 13,
      "font-weight": 700,
    }),
    textElement("공급자 집중도 (HHI)", {
      x: 18,
      y: 24,
      fill: "#293a4c",
      "font-size": 13,
      "font-weight": 700,
    }),
  );

  data.forEach((record) => {
    const selected = record.product === state.profile.productGroup;
    const radius = record.scaleBand === "대" ? 19 : record.scaleBand === "중" ? 15 : 11;
    const group = svgElement("g");
    group.append(
      svgElement("circle", {
        cx: x(record.growthPct),
        cy: y(record.hhi),
        r: radius,
        fill: selected ? "#087f78" : "#5f86b3",
        "fill-opacity": selected ? 0.95 : 0.72,
        stroke: selected ? "#12345b" : "#ffffff",
        "stroke-width": selected ? 4 : 2,
      }),
      textElement(record.product, {
        x: x(record.growthPct),
        y: y(record.hhi) - radius - 7,
        "text-anchor": "middle",
        fill: "#293a4c",
        "font-size": selected ? 13 : 11,
        "font-weight": selected ? 800 : 650,
      }),
    );
    const title = svgElement("title");
    title.textContent = `${record.product}: ${growthBand(record.growthPct)}, 공급자 집중도 ${concentrationBand(record.hhi)}, 공급자 ${supplierCountBand(record.supplierCount)}`;
    group.append(title);
    svg.append(group);
  });
}

function renderOpportunityTable() {
  const records = [...scenario().opportunities].sort((a, b) => b.growthPct - a.growthPct);
  elements.opportunityTable.innerHTML = `
    <table>
      <thead>
        <tr>
          <th scope="col">품목군</th>
          <th scope="col">최근 변화</th>
          <th scope="col">집중도</th>
          <th scope="col">공급자 규모</th>
          <th scope="col">읽는 방법</th>
        </tr>
      </thead>
      <tbody>
        ${records
          .map(
            (record) => `
              <tr>
                <td><strong>${record.product}</strong></td>
                <td>${growthBand(record.growthPct)}</td>
                <td>${concentrationBand(record.hhi)}</td>
                <td>${supplierCountBand(record.supplierCount)}</td>
                <td>${opportunityInterpretation(record)}</td>
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderSimilarGroups() {
  elements.similarGroups.innerHTML = scenario().similarGroups
    .map(
      (group) => `
        <article class="insight-card">
          <h4>${group.name} <span class="status status-normal">${shareBand(group.share)} 비중 예시</span></h4>
          <p>${group.description}</p>
          <p><strong>주요 특징:</strong> ${group.traits.join(" · ")}</p>
        </article>
      `,
    )
    .join("");
}

function renderQuestions() {
  const selected =
    scenario().opportunities.find((record) => record.product === state.profile.productGroup) ||
    scenario().opportunities[0];
  const concentration =
    selected.hhi > 0.25 ? "소수 공급자 집중이 함께 나타납니다" : "공급자가 비교적 다양합니다";
  const direction = selected.growthPct >= 0 ? "증가" : "감소";
  const questions = [
    {
      title: `${selected.product} 활동 ${direction}`,
      text: `최근 활동이 ${growthBand(selected.growthPct)}했고 ${concentration}. 이 변화가 신규 거래처, 품목 전환 또는 보고 방식 변화와 관련 있는지 확인해 보세요.`,
    },
    {
      title: `${state.profile.region} 비교 범위 확인`,
      text: "선택 권역의 기업 수가 적으면 결과 범위를 더 넓혀야 합니다. 전국 비교와 권역 비교 중 어떤 기준이 업무에 더 유용한지 검토해 보세요.",
    },
    {
      title: "기업군 정의 확인",
      text: `${state.profile.businessType}·${state.profile.productGroup} 조건이 실제 동종 기업을 잘 묶는지, 추가로 필요한 구분 기준이 있는지 확인해 보세요.`,
    },
  ];
  elements.reviewQuestions.innerHTML = questions
    .map(
      (question, index) => `
        <article class="insight-card">
          <p class="eyebrow">확인 질문 ${index + 1}</p>
          <h4>${question.title}</h4>
          <p>${question.text}</p>
        </article>
      `,
    )
    .join("");
}

function renderPrivacy() {
  elements.privacyMessage.textContent = state.data.privacy.message;
  elements.hiddenFieldList.innerHTML = state.data.privacy.hiddenFields
    .map((field) => `<li>${field}</li>`)
    .join("");
  elements.limitationList.innerHTML = state.data.limitations
    .map((limitation) => `<li>${limitation}</li>`)
    .join("");
}

function renderAll() {
  renderSummary();
  renderConclusion();
  updateProfileSteps();
  elements.resultPanel.hidden = isSuppressedProfile();
  if (isSuppressedProfile()) {
    updateFlowSteps();
    return;
  }
  renderMetrics();
  renderTrendChart();
  renderOpportunityChart();
  renderOpportunityTable();
  renderSimilarGroups();
  renderQuestions();
  updateFlowSteps();
}

function activateTab(tab) {
  elements.tabs.forEach((candidate) => {
    const selected = candidate === tab;
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  elements.panels.forEach((panel) => {
    panel.hidden = panel.id !== tab.getAttribute("aria-controls");
  });
  updateFlowSteps();
}

function bindTabs() {
  elements.tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      let nextIndex = index;
      if (event.key === "ArrowLeft") nextIndex = (index - 1 + elements.tabs.length) % elements.tabs.length;
      if (event.key === "ArrowRight") nextIndex = (index + 1) % elements.tabs.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = elements.tabs.length - 1;
      activateTab(elements.tabs[nextIndex]);
      elements.tabs[nextIndex].focus();
    });
  });
}

function readProfile() {
  state.profile = {
    businessType: elements.businessType.value,
    region: elements.region.value,
    productGroup: elements.productGroup.value,
  };
}

async function init() {
  const response = await fetch("./data/mock_data.json");
  if (!response.ok) throw new Error("Class 3 mock data could not be loaded.");
  state.data = await response.json();
  const options = state.data.profileOptions;
  fillOptions(elements.businessType, options.businessTypes, state.profile.businessType);
  fillOptions(elements.region, options.regions, state.profile.region);
  fillProductOptions(
    elements.productGroup,
    options.deviceTaxonomy || [{ group: "품목", items: options.productGroups }],
    state.profile.productGroup,
  );
  elements.applyProfile.addEventListener("click", () => {
    readProfile();
    state.profileApplied = true;
    renderAll();
    elements.conclusionCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  [elements.businessType, elements.region, elements.productGroup].forEach((field) => {
    field.addEventListener("focus", () => {
      state.profileApplied = false;
      updateProfileSteps();
    });
    field.addEventListener("change", () => {
      state.profileApplied = false;
      updateProfileSteps();
    });
  });
  window.addEventListener("scroll", updateFlowSteps, { passive: true });
  window.addEventListener("resize", updateFlowSteps, { passive: true });
  bindTabs();
  renderPrivacy();
  updateProfileSteps();
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
