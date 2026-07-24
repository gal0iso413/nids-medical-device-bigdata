const state = {
  data: null,
  profile: {
    businessType: "판매·임대업체",
    region: "수도권",
    productGroup: "B2. 임상화학검사기기",
  },
  profileApplied: false,
  phase: "profile",
};

const elements = {
  businessType: document.getElementById("businessType"),
  region: document.getElementById("region"),
  productGroup: document.getElementById("productGroup"),
  applyProfile: document.getElementById("applyProfile"),
  wizardRibbon: document.getElementById("wizardRibbon"),
  progressRail: document.getElementById("progressRail"),
  phaseProfile: document.getElementById("phase-profile"),
  resultStack: document.getElementById("resultStack"),
  suppressedPanel: document.getElementById("suppressedPanel"),
  phaseDepth: document.getElementById("phase-depth"),
  portraitHeading: document.getElementById("portrait-heading"),
  portraitDescription: document.getElementById("portraitDescription"),
  portraitTraits: document.getElementById("portraitTraits"),
  portraitMeta: document.getElementById("portraitMeta"),
  reportSubtitle: document.getElementById("reportSubtitle"),
  positionSentence: document.getElementById("positionSentence"),
  reportMetrics: document.getElementById("reportMetrics"),
  changeSentence: document.getElementById("changeSentence"),
  trendChart: document.getElementById("trendChart"),
  reviewQuestions: document.getElementById("reviewQuestions"),
  reportLimit: document.getElementById("reportLimit"),
  opportunityChart: document.getElementById("opportunityChart"),
  opportunityTable: document.getElementById("opportunityTable"),
  similarGroups: document.getElementById("similarGroups"),
  privacyMessage: document.getElementById("privacyMessage"),
  hiddenFieldList: document.getElementById("hiddenFieldList"),
  limitationList: document.getElementById("limitationList"),
  openDepth: document.getElementById("openDepth"),
  backToProfile: document.getElementById("backToProfile"),
  backToReport: document.getElementById("backToReport"),
  resetSuppressed: document.getElementById("resetSuppressed"),
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

function growthBand(value) {
  const direction = value >= 0 ? "증가" : "감소";
  const absolute = Math.abs(value);
  const lower = Math.floor(absolute / 5) * 5;
  return `${lower}~${lower + 5}% ${direction}`;
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

function shareBand(value) {
  const lower = Math.floor(value / 5) * 5;
  return `${lower}~${lower + 5}%`;
}

function displayMetricValue(metric) {
  if (metric.label === "거래 활동 변화") return growthBand(Number.parseFloat(metric.value));
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

function opportunityInterpretation(record) {
  const growth = record.growthPct >= 0 ? "증가" : "감소";
  const concentration =
    record.hhi > 0.25 ? "집중도가 높음" : record.hhi > 0.15 ? "집중도 보통" : "공급자 다양";
  return `${growth} · ${concentration}`;
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function scrollToEl(el) {
  if (!el) return;
  const top = window.scrollY + el.getBoundingClientRect().top - 80;
  window.scrollTo({
    top: Math.max(0, top),
    behavior: prefersReducedMotion() ? "auto" : "smooth",
  });
}

function updateFlowChrome() {
  const order = ["profile", "report", "depth"];
  const activeIndex = order.indexOf(state.phase);
  elements.progressRail.querySelectorAll("button").forEach((step) => {
    const id = step.dataset.phase;
    const stepIndex = order.indexOf(id);
    step.classList.remove("is-done");
    step.removeAttribute("aria-current");
    step.disabled = !state.profileApplied && id !== "profile";
    if (stepIndex === activeIndex) step.setAttribute("aria-current", "step");
    else if (state.profileApplied && stepIndex < activeIndex) step.classList.add("is-done");
  });
}

function updateWizardHighlight() {
  const focusMap = { businessType: 0, region: 1, productGroup: 2 };
  const active = focusMap[document.activeElement?.id] ?? 0;
  [...elements.wizardRibbon.children].forEach((cell, index) => {
    cell.classList.toggle("is-active", index === active);
  });
}

function setPhase(phase) {
  state.phase = phase;
  elements.phaseProfile.hidden = phase !== "profile";
  if (phase === "profile") {
    elements.resultStack.hidden = true;
    elements.phaseDepth.hidden = true;
    elements.suppressedPanel.hidden = true;
  }
  updateFlowChrome();
}

function readProfile() {
  state.profile = {
    businessType: elements.businessType.value,
    region: elements.region.value,
    productGroup: elements.productGroup.value,
  };
}

function showResults() {
  readProfile();
  state.profileApplied = true;

  if (isSuppressedProfile()) {
    elements.resultStack.hidden = true;
    elements.phaseProfile.hidden = true;
    elements.suppressedPanel.hidden = false;
    state.phase = "profile";
    updateFlowChrome();
    scrollToEl(elements.suppressedPanel);
    return;
  }

  elements.suppressedPanel.hidden = true;
  elements.phaseProfile.hidden = true;
  elements.resultStack.hidden = false;
  elements.phaseDepth.hidden = true;
  state.phase = "report";
  renderAllResults();
  updateFlowChrome();
  scrollToEl(document.getElementById("phase-portrait"));
}

function openDepth() {
  elements.phaseDepth.hidden = false;
  state.phase = "depth";
  const mapPanel = document.getElementById("depth-map");
  if (mapPanel) mapPanel.open = true;
  renderDepth();
  updateFlowChrome();
  scrollToEl(elements.phaseDepth);
}

function backToReport() {
  elements.phaseDepth.hidden = true;
  state.phase = "report";
  updateFlowChrome();
  scrollToEl(document.getElementById("phase-report"));
}

function backToProfile() {
  state.profileApplied = false;
  setPhase("profile");
  scrollToEl(elements.phaseProfile);
}

function renderPortrait() {
  const primary = scenario().similarGroups[0];
  elements.portraitHeading.textContent = primary.name;
  elements.portraitDescription.textContent =
    `${primary.description} 같은 기준으로 묶인 비슷한 기업군입니다.`;
  elements.portraitTraits.innerHTML = primary.traits
    .slice(0, 3)
    .map((trait) => `<li>${trait}</li>`)
    .join("");
  elements.portraitMeta.textContent =
    `${state.profile.region} · ${state.profile.businessType} · ${state.profile.productGroup} · 비교군 ${cohortCountDisplay()} · 비중 예시 ${shareBand(primary.share)}`;
}

function renderReport() {
  const metrics = scenario().metrics;
  const activity = metrics.find((m) => m.label === "거래 활동 변화") || metrics[0];
  const breadth = metrics.find((m) => m.label === "취급 품목 폭") || metrics[1];

  elements.reportSubtitle.textContent =
    `${state.profile.region} ${state.profile.businessType} · ${state.profile.productGroup}`;
  elements.positionSentence.textContent =
    `비슷한 기업군 ${cohortCountDisplay()} 규모에서 거래 활동은 ${activity.position}에 해당합니다. 취급 품목 폭은 ${displayMetricValue(breadth)} 수준입니다.`;
  elements.changeSentence.textContent =
    `최근 거래 활동은 ${displayMetricValue(activity)} 흐름입니다. 선택 조건 평균과 같은 업태·권역 중앙값을 비교합니다.`;
  elements.reportLimit.textContent =
    state.data.limitations[0] || "간담회용 생성 예시이며 사업 결과를 보장하지 않습니다.";

  elements.reportMetrics.innerHTML = metrics
    .slice(0, 4)
    .map(
      (metric) => `
      <article>
        <p class="metric-label">${metric.label}</p>
        <p class="metric-value">${displayMetricValue(metric)}</p>
        <p class="metric-note ${positionClass(metric.position)}">${metric.position}</p>
      </article>`,
    )
    .join("");

  renderTrendChart();
  renderQuestions();
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
  const height = 280;
  const margin = { top: 20, right: 20, bottom: 40, left: 60 };
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
  for (let tick = 0; tick <= 3; tick += 1) {
    const value = min + ((max - min) * tick) / 3;
    const yPos = y(value);
    svg.append(
      svgElement("line", {
        x1: margin.left,
        y1: yPos,
        x2: width - margin.right,
        y2: yPos,
        stroke: "#e2e8f0",
      }),
      textElement(new Intl.NumberFormat("ko-KR", { notation: "compact" }).format(value), {
        x: margin.left - 8,
        y: yPos + 4,
        "text-anchor": "end",
        fill: "#64748b",
        "font-size": 12,
      }),
    );
  }
  data.forEach((row, index) => {
    svg.append(
      textElement(row.month.slice(2), {
        x: x(index),
        y: height - 12,
        "text-anchor": "middle",
        fill: "#64748b",
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
      stroke: "#94a3b8",
      "stroke-width": 3,
      "stroke-dasharray": "7 5",
    }),
  );
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
      text: `최근 활동이 ${growthBand(selected.growthPct)}했고 ${concentration}. 신규 거래처·품목 전환과 관련 있는지 확인해 보세요.`,
    },
    {
      title: `${state.profile.region} 비교 범위`,
      text: "권역 기업 수가 적으면 범위를 넓혀야 합니다. 전국 비교와 권역 비교 중 업무에 맞는 기준을 검토해 보세요.",
    },
    {
      title: "기업군 정의 확인",
      text: `${state.profile.businessType}·${state.profile.productGroup} 조건이 실제 동종 기업을 잘 묶는지 확인해 보세요.`,
    },
  ];
  elements.reviewQuestions.innerHTML = questions
    .map(
      (question, index) => `
      <article class="q-board">
        <p class="lab-eyebrow">확인 질문 ${index + 1}</p>
        <h4>${question.title}</h4>
        <p>${question.text}</p>
      </article>`,
    )
    .join("");
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
        stroke: tick === 0 ? "#94a3b8" : "#e2e8f0",
      }),
      textElement(`${tick}%`, {
        x: x(tick),
        y: height - 42,
        "text-anchor": "middle",
        fill: "#64748b",
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
        stroke: tick.value === 0.25 ? "#94a3b8" : "#e2e8f0",
        "stroke-dasharray": tick.value === 0.25 ? "6 4" : "",
      }),
      textElement(tick.label, {
        x: margin.left - 12,
        y: y(tick.value) + 4,
        "text-anchor": "end",
        fill: "#64748b",
        "font-size": 12,
      }),
    );
  });
  svg.append(
    textElement("최근 거래 활동 증감률 (%)", {
      x: margin.left + plotWidth / 2,
      y: height - 10,
      "text-anchor": "middle",
      fill: "#0f172a",
      "font-size": 13,
      "font-weight": 700,
    }),
    textElement("공급자 집중도", {
      x: 18,
      y: 24,
      fill: "#0f172a",
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
        stroke: selected ? "#003675" : "#ffffff",
        "stroke-width": selected ? 4 : 2,
      }),
      textElement(record.product, {
        x: x(record.growthPct),
        y: y(record.hhi) - radius - 7,
        "text-anchor": "middle",
        fill: "#0f172a",
        "font-size": selected ? 13 : 11,
        "font-weight": selected ? 800 : 650,
      }),
    );
    svg.append(group);
  });
}

function renderOpportunityTable() {
  const records = [...scenario().opportunities].sort((a, b) => b.growthPct - a.growthPct);
  elements.opportunityTable.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>품목군</th><th>최근 변화</th><th>집중도</th><th>공급자 규모</th><th>읽는 방법</th>
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
          </tr>`,
          )
          .join("")}
      </tbody>
    </table>`;
}

function renderSimilarGroups() {
  elements.similarGroups.innerHTML = scenario().similarGroups
    .map(
      (group) => `
      <article class="insight-card">
        <h4>${group.name} <span class="status status-normal">${shareBand(group.share)} 비중 예시</span></h4>
        <p>${group.description}</p>
        <p><strong>주요 특징:</strong> ${group.traits.join(" · ")}</p>
      </article>`,
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

function renderDepth() {
  renderOpportunityChart();
  renderOpportunityTable();
  renderSimilarGroups();
  renderPrivacy();
}

function renderAllResults() {
  renderPortrait();
  renderReport();
  renderDepth();
}

function bindDepthExclusive() {
  const panels = [...document.querySelectorAll(".depth-panel")];
  panels.forEach((panel) => {
    panel.addEventListener("toggle", () => {
      if (!panel.open) return;
      panels.forEach((other) => {
        if (other !== panel) other.open = false;
      });
    });
  });
}

function bindEvents() {
  elements.applyProfile.addEventListener("click", showResults);
  elements.openDepth.addEventListener("click", openDepth);
  elements.backToProfile.addEventListener("click", backToProfile);
  elements.backToReport.addEventListener("click", backToReport);
  elements.resetSuppressed.addEventListener("click", backToProfile);

  [elements.businessType, elements.region, elements.productGroup].forEach((field) => {
    field.addEventListener("focus", updateWizardHighlight);
    field.addEventListener("change", () => {
      state.profileApplied = false;
      updateWizardHighlight();
      updateFlowChrome();
    });
  });

  elements.progressRail.querySelectorAll("button").forEach((step) => {
    step.addEventListener("click", () => {
      if (step.disabled) return;
      const phase = step.dataset.phase;
      if (phase === "profile") backToProfile();
      else if (phase === "report" && state.profileApplied) {
        elements.phaseDepth.hidden = true;
        state.phase = "report";
        updateFlowChrome();
        scrollToEl(document.getElementById("phase-report"));
      } else if (phase === "depth" && state.profileApplied) openDepth();
    });
  });

  bindDepthExclusive();
}

async function init() {
  const response = await fetch("../class_3/data/mock_data.json");
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
  bindEvents();
  renderPrivacy();
  updateWizardHighlight();
  setPhase("profile");
}

init().catch((error) => {
  console.error(error);
  document.getElementById("main").innerHTML = `
    <section class="panel">
      <h2 class="title">예시 데이터를 불러오지 못했습니다.</h2>
      <p class="lead">저장소 루트에서 HTTP 서버를 실행했는지 확인해 주세요.</p>
    </section>`;
});
