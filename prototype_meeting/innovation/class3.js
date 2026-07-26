const state = {
  data: null,
  profile: {
    businessType: "판매(임대)업",
    region: "수도권",
    productGroup: "B2. 임상화학검사기기",
  },
  profileApplied: false,
  phase: "profile",
  selectedDeviceName: null,
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
  phaseDeviceSearch: document.getElementById("phase-device-search"),
  phaseDeviceReport: document.getElementById("phase-device-report"),
  reportSubtitle: document.getElementById("reportSubtitle"),
  macroSentence: document.getElementById("macroSentence"),
  macroStrip: document.getElementById("macroStrip"),
  positionSentence: document.getElementById("positionSentence"),
  reportMetrics: document.getElementById("reportMetrics"),
  changeSentence: document.getElementById("changeSentence"),
  thinHistoryNotice: document.getElementById("thinHistoryNotice"),
  trendChart: document.getElementById("trendChart"),
  trendLegend: document.getElementById("trendLegend"),
  firmDiagnosisBody: document.getElementById("firmDiagnosisBody"),
  reviewQuestions: document.getElementById("reviewQuestions"),
  reportLimit: document.getElementById("reportLimit"),
  opportunityChart: document.getElementById("opportunityChart"),
  opportunityTable: document.getElementById("opportunityTable"),
  similarGroups: document.getElementById("similarGroups"),
  privacyMessage: document.getElementById("privacyMessage"),
  hiddenFieldList: document.getElementById("hiddenFieldList"),
  limitationList: document.getElementById("limitationList"),
  openDeviceSearch: document.getElementById("openDeviceSearch"),
  openDeviceSearchMid: document.getElementById("openDeviceSearchMid"),
  scrollToMap: document.getElementById("scrollToMap"),
  privacyInline: document.getElementById("privacyInline"),
  backToProfile: document.getElementById("backToProfile"),
  resetSuppressed: document.getElementById("resetSuppressed"),
  deviceSearchInput: document.getElementById("deviceSearchInput"),
  deviceNameList: document.getElementById("deviceNameList"),
  suggestChips: document.getElementById("suggestChips"),
  applyDeviceSearch: document.getElementById("applyDeviceSearch"),
  backToFirmFromSearch: document.getElementById("backToFirmFromSearch"),
  deviceReportTitle: document.getElementById("deviceReportTitle"),
  deviceReportSubtitle: document.getElementById("deviceReportSubtitle"),
  deviceMacroSentence: document.getElementById("deviceMacroSentence"),
  deviceMacroStrip: document.getElementById("deviceMacroStrip"),
  deviceStatMetrics: document.getElementById("deviceStatMetrics"),
  deviceFlagStrip: document.getElementById("deviceFlagStrip"),
  deviceTrendChart: document.getElementById("deviceTrendChart"),
  deviceDiagnosisBody: document.getElementById("deviceDiagnosisBody"),
  searchAnotherDevice: document.getElementById("searchAnotherDevice"),
  backToFirmFromDevice: document.getElementById("backToFirmFromDevice"),
  resetFromDevice: document.getElementById("resetFromDevice"),
};

function scenario() {
  return state.data.scenarios[state.profile.businessType];
}

function deviceItems() {
  return state.data.deviceItems || [];
}

function findDevice(name) {
  return deviceItems().find((item) => item.name === name) || null;
}

function resolveDataQuality() {
  const rules = state.data.dataQualityRules || [];
  const match = rules.find(
    (rule) =>
      rule.businessType === state.profile.businessType &&
      rule.region === state.profile.region,
  );
  if (match) {
    return {
      dataStatus: match.dataStatus,
      historyMonths: match.historyMonths ?? 0,
    };
  }
  const current = scenario();
  return {
    dataStatus: current.dataStatus || "ok",
    historyMonths: current.historyMonths ?? 6,
  };
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
  return resolveDataQuality().dataStatus === "suppressed";
}

function isThinHistory() {
  return resolveDataQuality().dataStatus === "thinHistory";
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

function supplierBubbleRadius(count) {
  if (count >= 35) return 19;
  if (count >= 15) return 15;
  return 11;
}

function supplierSizeLabel(count) {
  if (count >= 35) return "대";
  if (count >= 15) return "중";
  return "소";
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
  const order = ["profile", "report", "device"];
  const suppressed = state.profileApplied && isSuppressedProfile();
  const activeIndex = suppressed
    ? 0
    : order.indexOf(state.phase === "device-search" || state.phase === "device-report" ? "device" : state.phase);
  elements.progressRail.classList.toggle("is-suppressed", suppressed);
  elements.progressRail.querySelectorAll("button").forEach((step) => {
    const id = step.dataset.phase;
    const stepIndex = order.indexOf(id);
    step.classList.remove("is-done", "is-blocked");
    step.removeAttribute("aria-current");
    const unlocked =
      id === "profile" ||
      (state.profileApplied && id === "report" && !suppressed) ||
      (state.profileApplied && id === "device" && !suppressed);
    step.disabled = !unlocked;
    if (suppressed && id !== "profile") step.classList.add("is-blocked");
    if (stepIndex === activeIndex) step.setAttribute("aria-current", "step");
    else if (unlocked && stepIndex < activeIndex) step.classList.add("is-done");
  });
}

function updateWizardHighlight() {
  const focusMap = { businessType: 0, region: 1, productGroup: 2 };
  const active = focusMap[document.activeElement?.id] ?? 0;
  [...elements.wizardRibbon.children].forEach((cell, index) => {
    cell.classList.toggle("is-active", index === active);
  });
}

function hideAllStages() {
  elements.phaseProfile.hidden = true;
  elements.resultStack.hidden = true;
  elements.suppressedPanel.hidden = true;
  elements.phaseDeviceSearch.hidden = true;
  elements.phaseDeviceReport.hidden = true;
}

function setPhase(phase) {
  state.phase = phase;
  hideAllStages();
  if (phase === "profile") {
    elements.phaseProfile.hidden = false;
  } else if (phase === "report") {
    elements.resultStack.hidden = false;
  } else if (phase === "device-search") {
    elements.phaseDeviceSearch.hidden = false;
  } else if (phase === "device-report") {
    elements.phaseDeviceReport.hidden = false;
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
  state.selectedDeviceName = null;

  if (isSuppressedProfile()) {
    hideAllStages();
    elements.suppressedPanel.hidden = false;
    state.phase = "profile";
    updateFlowChrome();
    scrollToEl(elements.suppressedPanel);
    return;
  }

  setPhase("report");
  renderFirmReport();
  ensureMapOpen();
  scrollToEl(document.getElementById("phase-report"));
}

function ensureMapOpen() {
  const map = document.getElementById("depth-map");
  if (map) map.open = true;
}

function scrollToMap() {
  ensureMapOpen();
  const map = document.getElementById("depth-map");
  scrollToEl(map || elements.opportunityChart);
}

function backToProfile() {
  state.profileApplied = false;
  state.selectedDeviceName = null;
  setPhase("profile");
  scrollToEl(elements.phaseProfile);
}

function openDeviceSearch() {
  setPhase("device-search");
  renderDeviceSearch();
  scrollToEl(elements.phaseDeviceSearch);
}

function backToFirmReport() {
  setPhase("report");
  ensureMapOpen();
  scrollToEl(document.getElementById("phase-report"));
}

function buildFirmDiagnosis() {
  const metrics = scenario().metrics;
  const activity = metrics.find((m) => m.label === "거래 활동 변화") || metrics[0];
  const selected =
    scenario().opportunities.find((record) => record.product === state.profile.productGroup) ||
    scenario().opportunities[0];
  const observed = `해당 기업군 ${cohortCountDisplay()} 규모에서 거래 활동은 ${activity.position}, 관심 품목군(${state.profile.productGroup}) 최근 변화는 ${growthBand(selected.growthPct)}입니다.`;
  let interpretation = "선택 조건 평균이 같은 업종·권역 기준선과 비슷한 흐름입니다.";
  if (activity.position.includes("상위")) {
    interpretation = "같은 조건 기업군 대비 거래 활동이 상위 구간에 있습니다.";
  } else if (activity.position.includes("하위")) {
    interpretation = "같은 조건 기업군 대비 거래 활동이 하위 구간에 있습니다.";
  }
  if (selected.hhi > 0.25) {
    interpretation += " 관심 품목군은 공급자 집중도가 높은 편입니다.";
  }
  const caution = isThinHistory()
    ? "비교 기간이 짧아 추이 해석은 제한적으로 보세요. 권역·업종 조건을 넓혀 재확인할 수 있습니다."
    : "사업 결과가 보장되지 않습니다. 신규 거래처·보고 방식 변화 여부를 내부에서 검증해 보세요.";
  return { observed, interpretation, caution };
}

function buildDeviceDiagnosis(item) {
  const stats = item.stats;
  const observed = `${item.name}의 최근 활동은 ${growthBand(stats.growthPct)}, 공급자 집중도는 ${stats.concentrationBand}, 공급자 규모는 ${stats.supplierCountBand} 수준입니다.`;
  let interpretation = "소속 품목군 대비 비중과 활동 방향을 함께 보면 시장 위치가 드러납니다.";
  if (stats.growthPct >= 10 && stats.hhi > 0.25) {
    interpretation = "활동이 늘면서 소수 공급자 집중도도 높은 구간입니다. 대체 조달·보고 변화를 점검할 여지가 있습니다.";
  } else if (stats.growthPct < 0) {
    interpretation = "최근 활동이 줄어든 구간입니다. 수요 변화인지 보고 공백인지 구분해 볼 필요가 있습니다.";
  } else if (stats.hhi <= 0.15) {
    interpretation = "공급자가 비교적 다양한 편입니다. 경쟁·유통 경로가 넓은 품목으로 읽을 수 있습니다.";
  }
  return {
    observed,
    interpretation,
    caution: `취급 맥락(집계): ${item.flagPrevalence.classMode}. 허가·UDI 색인이 아니라 통계 요약입니다.`,
  };
}

function renderDiagnosis(container, diagnosis) {
  container.innerHTML = `
    <dl class="diagnosis-dl">
      <div><dt>관측</dt><dd>${diagnosis.observed}</dd></div>
      <div><dt>해석</dt><dd>${diagnosis.interpretation}</dd></div>
      <div><dt>유의점</dt><dd>${diagnosis.caution}</dd></div>
    </dl>`;
}

function renderFirmReport() {
  const metrics = scenario().metrics;
  const activity = metrics.find((m) => m.label === "거래 활동 변화") || metrics[0];
  const breadth = metrics.find((m) => m.label === "취급 품목 폭") || metrics[1];
  const thin = isThinHistory();
  const primary = scenario().similarGroups[0];

  elements.reportSubtitle.textContent =
    `${state.profile.region} · ${state.profile.businessType} · 품목군 ${state.profile.productGroup}`;

  elements.macroSentence.textContent =
    `${primary.description} 해당 기업군 규모는 ${cohortCountDisplay()}입니다.`;
  elements.macroStrip.innerHTML = `
    <article><p class="metric-label">기업군 규모</p><p class="metric-value">${cohortCountDisplay()}</p></article>
    <article><p class="metric-label">거래 활동</p><p class="metric-value">${displayMetricValue(activity)}</p><p class="metric-note ${positionClass(activity.position)}">${activity.position}</p></article>
    <article><p class="metric-label">품목 폭</p><p class="metric-value">${displayMetricValue(breadth)}</p></article>`;

  elements.positionSentence.textContent =
    `해당 기업군에서 거래 활동은 ${activity.position}에 해당합니다. 취급 품목 폭은 ${displayMetricValue(breadth)} 수준입니다.`;
  elements.reportMetrics.innerHTML = metrics
    .map(
      (metric) => `
      <article>
        <p class="metric-label">${metric.label}</p>
        <p class="metric-value">${displayMetricValue(metric)}</p>
        <p class="metric-note ${positionClass(metric.position)}">${metric.position}</p>
      </article>`,
    )
    .join("");

  if (thin) {
    elements.changeSentence.textContent =
      "월별 추이를 안정적으로 비교하기에는 기간이 부족합니다. 아래 위치·범위 지표를 먼저 확인하세요.";
    elements.thinHistoryNotice.hidden = false;
    elements.trendChart.hidden = true;
    if (elements.trendLegend) elements.trendLegend.hidden = true;
    elements.trendChart.replaceChildren();
  } else {
    elements.changeSentence.textContent =
      `최근 거래 활동은 ${displayMetricValue(activity)} 흐름입니다. 선택 조건 평균과 같은 업종·권역 중앙값을 비교합니다.`;
    elements.thinHistoryNotice.hidden = true;
    elements.trendChart.hidden = false;
    if (elements.trendLegend) elements.trendLegend.hidden = false;
    renderTrendChart(elements.trendChart, scenario().transactionSeries, "profileAverage", "peerMedian");
  }

  renderDiagnosis(elements.firmDiagnosisBody, buildFirmDiagnosis());
  if (elements.privacyInline) {
    elements.privacyInline.textContent =
      "공개 원칙: 회사명·정확한 순위·소수 기업군 식별 가능 값은 숨깁니다. 아래는 해당 기업군 집계만 보여 줍니다.";
  }
  renderQuestions();
  renderOpportunityChart();
  renderOpportunityTable();
  renderSimilarGroups();
  renderPrivacy();
  ensureMapOpen();
  elements.reportLimit.textContent =
    state.data.limitations[0] || "간담회용 생성 예시이며 사업 결과를 보장하지 않습니다.";
}

function suggestedDevices() {
  const all = deviceItems();
  const linked = all.filter((item) => item.productGroup === state.profile.productGroup);
  const rest = all.filter((item) => item.productGroup !== state.profile.productGroup);
  return [...linked, ...rest];
}

function renderDeviceSearch() {
  const items = suggestedDevices();
  elements.deviceNameList.replaceChildren();
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.name;
    elements.deviceNameList.append(option);
  });

  const linked = items.filter((item) => item.productGroup === state.profile.productGroup);
  const rest = items.filter((item) => item.productGroup !== state.profile.productGroup);
  const chips = [...linked, ...rest].slice(0, 4);
  elements.suggestChips.innerHTML = chips
    .map(
      (item) => `
      <button type="button" class="chip" data-name="${item.name}" role="listitem">
        ${item.name}
        <span class="chip-meta">${item.suggestTags.slice(0, 2).join(" · ")}${
          item.productGroup === state.profile.productGroup ? " · 선택 품목군" : ""
        }</span>
      </button>`,
    )
    .join("");

  elements.suggestChips.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      elements.deviceSearchInput.value = chip.dataset.name;
      state.selectedDeviceName = chip.dataset.name;
      elements.applyDeviceSearch.disabled = false;
    });
  });

  const current = elements.deviceSearchInput.value.trim();
  const match = findDevice(current);
  state.selectedDeviceName = match ? match.name : null;
  elements.applyDeviceSearch.disabled = !match;
}

function applyDeviceSearch() {
  const query = elements.deviceSearchInput.value.trim();
  const item = findDevice(query);
  if (!item) {
    elements.applyDeviceSearch.disabled = true;
    return;
  }
  state.selectedDeviceName = item.name;
  renderDeviceReport(item);
  setPhase("device-report");
  scrollToEl(elements.phaseDeviceReport);
}

function renderDeviceReport(item) {
  const stats = item.stats;
  const flags = item.flagPrevalence;
  elements.deviceReportTitle.textContent = item.name;
  elements.deviceReportSubtitle.textContent =
    `품목명 통계 · 소속 품목군 ${item.productGroup} · 기업군 관심 품목군 ${state.profile.productGroup}`;

  elements.deviceMacroSentence.textContent =
    `${item.name}의 최근 공급 활동은 ${growthBand(stats.growthPct)}이며, 공급자 집중도는 ${stats.concentrationBand}입니다.`;
  elements.deviceMacroStrip.innerHTML = `
    <article><p class="metric-label">활동 증감</p><p class="metric-value">${growthBand(stats.growthPct)}</p></article>
    <article><p class="metric-label">공급자 집중도</p><p class="metric-value">${stats.concentrationBand}</p></article>
    <article><p class="metric-label">공급자 규모</p><p class="metric-value">${stats.supplierCountBand}</p></article>
    <article><p class="metric-label">품목군 내 비중</p><p class="metric-value">${shareBand(stats.shareOfGroupPct)}</p></article>`;

  const mix = stats.receiverMix;
  elements.deviceStatMetrics.innerHTML = `
    <article><p class="metric-label">공급 수량 방향</p><p class="metric-value">${stats.quantityDirection}</p></article>
    <article><p class="metric-label">수령 유형 · 의료기관</p><p class="metric-value">${shareBand(mix.의료기관)}</p></article>
    <article><p class="metric-label">수령 유형 · 판매(임대)</p><p class="metric-value">${shareBand(mix["판매(임대)"])}</p></article>
    <article><p class="metric-label">수령 유형 · 기타</p><p class="metric-value">${shareBand(mix.기타)}</p></article>`;

  elements.deviceFlagStrip.innerHTML = `
    <p class="flag-title">집계 비중 요약 (허가·UDI·모델 색인 화면이 아닙니다)</p>
    <ul class="flag-list">
      <li>등급 구성 비중: ${flags.classMode}</li>
      <li>추적관리 관련 비중: ${flags.traceableShare}</li>
      <li>이식형 관련 비중: ${flags.implantableShare}</li>
      <li>일회용 관련 비중: ${flags.singleUseShare}</li>
      <li>요양급여 관련 비중: ${flags.reimbursementShare}</li>
    </ul>`;

  renderTrendChart(elements.deviceTrendChart, stats.activitySeries, "itemAverage", "groupAverage");
  renderDiagnosis(elements.deviceDiagnosisBody, buildDeviceDiagnosis(item));
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

function renderTrendChart(svg, data, solidKey, dashedKey) {
  if (!svg || !data || data.length < 2) {
    if (svg) svg.replaceChildren();
    return;
  }
  const width = 900;
  const height = 280;
  const margin = { top: 20, right: 20, bottom: 40, left: 60 };
  const plotWidth = width - margin.left - margin.right;
  const allValues = data.flatMap((row) => [row[solidKey], row[dashedKey]]);
  const min = Math.floor(Math.min(...allValues) * 0.88);
  const max = Math.ceil(Math.max(...allValues) * 1.08);
  const x = (index) => margin.left + (index / (data.length - 1)) * plotWidth;
  const y = (value) => margin.top + ((max - value) / (max - min || 1)) * (height - margin.top - margin.bottom);
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
      d: pathFor(solidKey),
      fill: "none",
      stroke: "#087f78",
      "stroke-width": 4,
    }),
    svgElement("path", {
      d: pathFor(dashedKey),
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
      text: "권역 기업 수가 적으면 「전국」으로 넓혀 보세요. 수도권·비수도권·전국 중 업무에 맞는 기준을 검토해 보세요.",
    },
    {
      title: "품목명으로 이어보기",
      text: "품목군 다음 단계로, 관심 있는 품목명 통계를 보면 더 구체적인 시장 위치를 확인할 수 있습니다.",
    },
  ];
  if (isThinHistory()) {
    questions.unshift({
      title: "비교 기간 확인",
      text: "최근 거래 이력이 짧아 월별 추이는 숨겼습니다. 더 긴 기간이 쌓이면 변화 비교를 다시 확인해 보세요.",
    });
    questions.length = 3;
  }
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
  // x = HHI (concentration), y = growth %
  const xMin = 0;
  const xMax = 0.5;
  const yMin = -12;
  const yMax = 32;
  const x = (value) => margin.left + ((value - xMin) / (xMax - xMin)) * plotWidth;
  const y = (value) => margin.top + ((yMax - value) / (yMax - yMin)) * plotHeight;

  svg.replaceChildren();
  [
    { value: 0.1, label: "낮음" },
    { value: 0.25, label: "보통" },
    { value: 0.4, label: "높음" },
  ].forEach((tick) => {
    svg.append(
      svgElement("line", {
        x1: x(tick.value),
        y1: margin.top,
        x2: x(tick.value),
        y2: height - margin.bottom,
        stroke: tick.value === 0.25 ? "#94a3b8" : "#e2e8f0",
        "stroke-dasharray": tick.value === 0.25 ? "6 4" : "",
      }),
      textElement(tick.label, {
        x: x(tick.value),
        y: height - 42,
        "text-anchor": "middle",
        fill: "#64748b",
        "font-size": 12,
      }),
    );
  });
  [0, -10, 10, 20, 30].forEach((tick) => {
    svg.append(
      svgElement("line", {
        x1: margin.left,
        y1: y(tick),
        x2: width - margin.right,
        y2: y(tick),
        stroke: tick === 0 ? "#94a3b8" : "#e2e8f0",
      }),
      textElement(`${tick}%`, {
        x: margin.left - 12,
        y: y(tick) + 4,
        "text-anchor": "end",
        fill: "#64748b",
        "font-size": 12,
      }),
    );
  });
  svg.append(
    textElement("공급자 집중도 (낮음 → 높음)", {
      x: margin.left + plotWidth / 2,
      y: height - 10,
      "text-anchor": "middle",
      fill: "#0f172a",
      "font-size": 13,
      "font-weight": 700,
    }),
    textElement("최근 거래 활동 증감률 (%)", {
      x: 18,
      y: 24,
      fill: "#0f172a",
      "font-size": 13,
      "font-weight": 700,
    }),
  );

  // Bubble size legend (소 / 중 / 대)
  const legendX = width - margin.right - 118;
  const legendY = margin.top + 8;
  svg.append(
    svgElement("rect", {
      x: legendX - 8,
      y: legendY - 6,
      width: 126,
      height: 78,
      rx: 8,
      fill: "#ffffff",
      "fill-opacity": 0.92,
      stroke: "#e2e8f0",
    }),
    textElement("거품 = 공급자 수", {
      x: legendX,
      y: legendY + 10,
      fill: "#0f172a",
      "font-size": 11,
      "font-weight": 700,
    }),
  );
  [
    { label: "소 <15", count: 10, dy: 28 },
    { label: "중 15–34", count: 22, dy: 48 },
    { label: "대 ≥35", count: 40, dy: 68 },
  ].forEach((row) => {
    const r = supplierBubbleRadius(row.count);
    svg.append(
      svgElement("circle", {
        cx: legendX + 12,
        cy: legendY + row.dy,
        r,
        fill: "#5f86b3",
        "fill-opacity": 0.75,
        stroke: "#ffffff",
        "stroke-width": 1.5,
      }),
      textElement(row.label, {
        x: legendX + 28,
        y: legendY + row.dy + 4,
        fill: "#334155",
        "font-size": 11,
      }),
    );
  });

  data.forEach((record) => {
    const selected = record.product === state.profile.productGroup;
    const radius = supplierBubbleRadius(record.supplierCount);
    const group = svgElement("g");
    group.append(
      svgElement("circle", {
        cx: x(record.hhi),
        cy: y(record.growthPct),
        r: radius,
        fill: selected ? "#087f78" : "#5f86b3",
        "fill-opacity": selected ? 0.95 : 0.72,
        stroke: selected ? "#003675" : "#ffffff",
        "stroke-width": selected ? 4 : 2,
      }),
      textElement(record.product, {
        x: x(record.hhi),
        y: y(record.growthPct) - radius - 7,
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
    <p class="meta" style="margin-bottom:8px">거품 크기 = 공급자 수 (소 &lt;15 · 중 15–34 · 대 ≥35)</p>
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
            <td>${supplierCountBand(record.supplierCount)} (${supplierSizeLabel(record.supplierCount)})</td>
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

function bindDepthExclusive() {
  const panels = [...document.querySelectorAll("#firmReact .depth-panel")];
  const map = document.getElementById("depth-map");
  panels.forEach((panel) => {
    panel.addEventListener("toggle", () => {
      if (!panel.open) return;
      // Keep the map available during the meeting; only exclusivity among other panels.
      panels.forEach((other) => {
        if (other === panel || other === map) return;
        other.open = false;
      });
    });
  });
}

function bindEvents() {
  elements.applyProfile.addEventListener("click", showResults);
  elements.openDeviceSearch.addEventListener("click", openDeviceSearch);
  if (elements.openDeviceSearchMid) {
    elements.openDeviceSearchMid.addEventListener("click", openDeviceSearch);
  }
  if (elements.scrollToMap) {
    elements.scrollToMap.addEventListener("click", scrollToMap);
  }
  elements.backToProfile.addEventListener("click", backToProfile);
  elements.resetSuppressed.addEventListener("click", backToProfile);
  elements.applyDeviceSearch.addEventListener("click", applyDeviceSearch);
  elements.backToFirmFromSearch.addEventListener("click", backToFirmReport);
  elements.backToFirmFromDevice.addEventListener("click", backToFirmReport);
  elements.searchAnotherDevice.addEventListener("click", openDeviceSearch);
  elements.resetFromDevice.addEventListener("click", backToProfile);

  elements.deviceSearchInput.addEventListener("input", () => {
    const match = findDevice(elements.deviceSearchInput.value.trim());
    state.selectedDeviceName = match ? match.name : null;
    elements.applyDeviceSearch.disabled = !match;
  });

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
      else if (phase === "report" && state.profileApplied && !isSuppressedProfile()) backToFirmReport();
      else if (phase === "device" && state.profileApplied && !isSuppressedProfile()) {
        if (state.selectedDeviceName && findDevice(state.selectedDeviceName)) {
          renderDeviceReport(findDevice(state.selectedDeviceName));
          setPhase("device-report");
          scrollToEl(elements.phaseDeviceReport);
        } else {
          openDeviceSearch();
        }
      }
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
