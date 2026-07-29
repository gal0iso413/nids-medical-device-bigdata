const state = {
  data: null,
  profile: {
    businessType: "판매(임대)업",
    region: "수도권",
    productGroup: "B2. 임상화학검사기기",
  },
  profileApplied: false,
  selectedDeviceName: null,
};

const elements = {
  businessType: document.getElementById("businessType"),
  region: document.getElementById("region"),
  productGroup: document.getElementById("productGroup"),
  applyProfile: document.getElementById("applyProfile"),
  profileSteps: document.getElementById("profileSteps"),
  conclusionCard: document.getElementById("conclusionCard"),
  conclusionHeadline: document.getElementById("conclusionHeadline"),
  conclusionBody: document.getElementById("conclusionBody"),
  flowSteps: document.getElementById("flowSteps"),
  cohortSummary: document.getElementById("cohortSummary"),
  resultPanel: document.getElementById("resultPanel"),
  cohortMetrics: document.getElementById("cohortMetrics"),
  thinHistoryNotice: document.getElementById("thinHistoryNotice"),
  trendChart: document.getElementById("trendChart"),
  trendCaption: document.getElementById("trendCaption"),
  opportunityChart: document.getElementById("opportunityChart"),
  opportunityTable: document.getElementById("opportunityTable"),
  similarGroups: document.getElementById("similarGroups"),
  reviewQuestions: document.getElementById("reviewQuestions"),
  privacyMessage: document.getElementById("privacyMessage"),
  hiddenFieldList: document.getElementById("hiddenFieldList"),
  limitationList: document.getElementById("limitationList"),
  openDeviceTab: document.getElementById("openDeviceTab"),
  deviceSearchInput: document.getElementById("deviceSearchInput"),
  deviceNameList: document.getElementById("deviceNameList"),
  suggestChips: document.getElementById("suggestChips"),
  applyDeviceSearch: document.getElementById("applyDeviceSearch"),
  backToFirmFromDevice: document.getElementById("backToFirmFromDevice"),
  backToFirmFromDeviceReport: document.getElementById("backToFirmFromDeviceReport"),
  searchAnotherDevice: document.getElementById("searchAnotherDevice"),
  deviceReport: document.getElementById("deviceReport"),
  deviceReportTitle: document.getElementById("deviceReportTitle"),
  deviceReportSubtitle: document.getElementById("deviceReportSubtitle"),
  deviceMacroSentence: document.getElementById("deviceMacroSentence"),
  deviceMacroStrip: document.getElementById("deviceMacroStrip"),
  deviceStatMetrics: document.getElementById("deviceStatMetrics"),
  deviceFlagStrip: document.getElementById("deviceFlagStrip"),
  deviceTrendChart: document.getElementById("deviceTrendChart"),
  deviceDiagnosisBody: document.getElementById("deviceDiagnosisBody"),
  tabs: [...document.querySelectorAll('[role="tab"]')],
  panels: [...document.querySelectorAll('[role="tabpanel"]')],
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

function displayMetricValue(metric) {
  if (metric.label === "거래 활동 변화") {
    return growthBand(Number.parseFloat(metric.value));
  }
  if (metric.label === "취급 품목 폭") {
    const value = Number.parseInt(metric.value, 10);
    return `${Math.max(1, value - 4)}~${value + 4}개`;
  }
  if (metric.label === "거래처 폭") {
    const value = Number.parseInt(metric.value, 10);
    return `${Math.max(1, value - 4)}~${value + 4}개`;
  }
  return metric.value;
}

function renderConclusion() {
  if (isSuppressedProfile()) {
    elements.conclusionHeadline.textContent = "해당 기업군을 공개 기준으로 표시할 수 없습니다";
    elements.conclusionBody.textContent =
      "기업·기관 수가 공개 기준보다 적은 예시입니다. 권역을 「전국」으로 넓히거나 업종 조건을 완화해 주세요.";
    return;
  }

  const metrics = scenario().metrics;
  const activity = metrics.find((metric) => metric.label === "거래 활동 변화") || metrics[0];
  const breadth = metrics.find((metric) => metric.label === "취급 품목 폭") || metrics[1];
  const thinNote = isThinHistory()
    ? " 비교 기간이 짧아 월별 추이는 표시하지 않습니다."
    : "";

  elements.conclusionHeadline.textContent =
    `${state.profile.region} ${state.profile.businessType} 기준, 거래 활동은 ${activity.position}에 해당합니다`;
  elements.conclusionBody.innerHTML =
    `<span class="conclusion-line"><strong>위치:</strong> ${state.profile.productGroup} 관심 해당 기업군 ${cohortCountDisplay()} 규모.</span>` +
    `<span class="conclusion-line"><strong>변화:</strong> 거래 활동 ${displayMetricValue(activity)} (${activity.position}).</span>` +
    `<span class="conclusion-line"><strong>확인:</strong> 취급 품목(품목명) 폭은 ${displayMetricValue(breadth)} 수준입니다.${thinNote} ` +
    `「확인할 사항」 또는 「품목명 통계」 탭에서 이어서 살펴보세요.</span>`;
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
  if (tabId === "tab-questions" || tabId === "tab-device") active = "check";
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
      <h3>해당 기업군을 공개 기준으로 표시할 수 없습니다</h3>
      <p>
        해당 조건은 기업·기관 수가 공개 기준보다 적은 예시입니다.
        권역을 「전국」으로 넓히거나 업종 조건을 완화해 주세요.
      </p>
    `;
    return;
  }
  const thinNote = isThinHistory()
    ? " 최근 거래 이력이 짧아 월별 추이는 숨깁니다."
    : "";
  elements.cohortSummary.innerHTML = `
    <p class="eyebrow">현재 비교 기준</p>
    <h3>${state.profile.region} · ${state.profile.businessType}</h3>
    <p>
      <strong>${state.profile.productGroup}</strong>에 관심이 있는
      <strong>해당 기업군 ${cohortCountDisplay()} 규모</strong>의 생성 예시 집계입니다.
      개별 업체의 값이나 순위는 표시하지 않습니다.${thinNote}
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
  const thin = isThinHistory();

  if (elements.thinHistoryNotice) {
    elements.thinHistoryNotice.hidden = !thin;
  }
  if (elements.trendCaption) {
    elements.trendCaption.hidden = thin;
  }

  if (thin) {
    svg.hidden = true;
    svg.replaceChildren();
    return;
  }

  svg.hidden = false;
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
    textElement("같은 업종·권역 중앙값", { x: 697, y: 22, fill: "#293a4c", "font-size": 12 }),
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
  const xMin = 0;
  const xMax = 0.5;
  const yMin = -12;
  const yMax = 32;
  const x = (value) => margin.left + ((value - xMin) / (xMax - xMin)) * plotWidth;
  const y = (value) => margin.top + ((yMax - value) / (yMax - yMin)) * (height - margin.top - margin.bottom);

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
        stroke: tick.value === 0.25 ? "#8da0b3" : "#d7e0e8",
        "stroke-dasharray": tick.value === 0.25 ? "6 4" : "",
      }),
      textElement(tick.label, {
        x: x(tick.value),
        y: height - 42,
        "text-anchor": "middle",
        fill: "#536273",
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
        stroke: tick === 0 ? "#8da0b3" : "#d7e0e8",
      }),
      textElement(`${tick}%`, {
        x: margin.left - 12,
        y: y(tick) + 4,
        "text-anchor": "end",
        fill: "#536273",
        "font-size": 12,
      }),
    );
  });

  svg.append(
    textElement("공급자 집중도 (낮음 → 높음)", {
      x: margin.left + plotWidth / 2,
      y: height - 10,
      "text-anchor": "middle",
      fill: "#293a4c",
      "font-size": 13,
      "font-weight": 700,
    }),
    textElement("최근 거래 활동 증감률 (%)", {
      x: 18,
      y: 24,
      fill: "#293a4c",
      "font-size": 13,
      "font-weight": 700,
    }),
  );

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
      stroke: "#d7e0e8",
    }),
    textElement("거품 = 공급자 수", {
      x: legendX,
      y: legendY + 10,
      fill: "#293a4c",
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
        fill: "#536273",
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
        stroke: selected ? "#12345b" : "#ffffff",
        "stroke-width": selected ? 4 : 2,
      }),
      textElement(record.product, {
        x: x(record.hhi),
        y: y(record.growthPct) - radius - 7,
        "text-anchor": "middle",
        fill: "#293a4c",
        "font-size": selected ? 13 : 11,
        "font-weight": selected ? 800 : 650,
      }),
    );
    const title = svgElement("title");
    title.textContent = `${record.product}: ${growthBand(record.growthPct)}, 공급자 집중도 ${concentrationBand(record.hhi)}, 공급자 ${supplierCountBand(record.supplierCount)} (${supplierSizeLabel(record.supplierCount)})`;
    group.append(title);
    svg.append(group);
  });
}

function renderOpportunityTable() {
  const records = [...scenario().opportunities].sort((a, b) => b.growthPct - a.growthPct);
  elements.opportunityTable.innerHTML = `
    <p class="panel-description">거품 크기 = 공급자 수 (소 &lt;15 · 중 15–34 · 대 ≥35)</p>
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
                <td>${supplierCountBand(record.supplierCount)} (${supplierSizeLabel(record.supplierCount)})</td>
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
      text: "선택 권역의 기업 수가 적으면 「전국」으로 범위를 넓혀 보세요. 수도권·비수도권·전국 중 업무에 맞는 기준을 검토해 보세요.",
    },
    {
      title: "품목명으로 이어보기",
      text: "품목군 다음 단계로 「품목명 통계」 탭에서 관심 품목명 집계를 보면 더 구체적인 시장 위치를 확인할 수 있습니다. 색인(index) 조회가 아닙니다.",
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
        <article class="insight-card">
          <p class="eyebrow">확인 질문 ${index + 1}</p>
          <h4>${question.title}</h4>
          <p>${question.text}</p>
        </article>
      `,
    )
    .join("");
}

function suggestedDevices() {
  const all = deviceItems();
  const linked = all.filter((item) => item.productGroup === state.profile.productGroup);
  const rest = all.filter((item) => item.productGroup !== state.profile.productGroup);
  return [...linked, ...rest];
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
    caution:
      "이 화면은 공급·거래 집계 통계 요약입니다. 품목 허가·UDI·모델 목록 같은 등록정보 색인(index)이 아닙니다.",
  };
}

function renderDiagnosis(container, diagnosis) {
  if (!container) return;
  container.innerHTML = `
    <dl class="diagnosis-dl">
      <div><dt>관측</dt><dd>${diagnosis.observed}</dd></div>
      <div><dt>해석</dt><dd>${diagnosis.interpretation}</dd></div>
      <div><dt>유의점</dt><dd>${diagnosis.caution}</dd></div>
    </dl>`;
}

function renderDeviceTrendChart(data) {
  const svg = elements.deviceTrendChart;
  if (!svg || !data || data.length < 2) {
    if (svg) svg.replaceChildren();
    return;
  }
  const solidKey = "itemAverage";
  const dashedKey = "groupAverage";
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
        stroke: "#d7e0e8",
      }),
      textElement(new Intl.NumberFormat("ko-KR", { notation: "compact" }).format(value), {
        x: margin.left - 8,
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
        y: height - 12,
        "text-anchor": "middle",
        fill: "#536273",
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
      stroke: "#718096",
      "stroke-width": 3,
      "stroke-dasharray": "7 5",
    }),
  );
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

function renderDeviceReport(item) {
  const stats = item.stats;
  const flags = item.flagPrevalence;
  elements.deviceReport.hidden = false;
  elements.deviceReportTitle.textContent = item.name;
  elements.deviceReportSubtitle.textContent =
    `품목명 통계 · 소속 품목군 ${item.productGroup} · 기업군 관심 품목군 ${state.profile.productGroup}`;
  elements.deviceMacroSentence.textContent =
    `${item.name}의 최근 공급 활동은 ${growthBand(stats.growthPct)}이며, 공급자 집중도는 ${stats.concentrationBand}입니다.`;
  elements.deviceMacroStrip.innerHTML = `
    <article class="metric"><p class="metric-label">활동 증감</p><p class="metric-value">${growthBand(stats.growthPct)}</p></article>
    <article class="metric"><p class="metric-label">공급자 집중도</p><p class="metric-value">${stats.concentrationBand}</p></article>
    <article class="metric"><p class="metric-label">공급자 규모</p><p class="metric-value">${stats.supplierCountBand}</p></article>
    <article class="metric"><p class="metric-label">품목군 내 비중</p><p class="metric-value">${shareBand(stats.shareOfGroupPct)}</p></article>`;

  const mix = stats.receiverMix;
  elements.deviceStatMetrics.innerHTML = `
    <article class="metric"><p class="metric-label">공급 수량 방향</p><p class="metric-value">${stats.quantityDirection}</p></article>
    <article class="metric"><p class="metric-label">수령 유형 · 의료기관</p><p class="metric-value">${shareBand(mix.의료기관)}</p></article>
    <article class="metric"><p class="metric-label">수령 유형 · 판매(임대)</p><p class="metric-value">${shareBand(mix["판매(임대)"])}</p></article>
    <article class="metric"><p class="metric-label">수령 유형 · 기타</p><p class="metric-value">${shareBand(mix.기타)}</p></article>`;

  elements.deviceFlagStrip.innerHTML = `
    <p class="flag-title">집계 비중 요약 (허가·UDI·모델 색인 화면이 아닙니다)</p>
    <ul class="flag-list">
      <li>등급 구성 비중: ${flags.classMode}</li>
      <li>추적관리 관련 비중: ${flags.traceableShare}</li>
      <li>이식형 관련 비중: ${flags.implantableShare}</li>
      <li>일회용 관련 비중: ${flags.singleUseShare}</li>
      <li>요양급여 관련 비중: ${flags.reimbursementShare}</li>
    </ul>`;

  renderDeviceTrendChart(stats.activitySeries);
  renderDiagnosis(elements.deviceDiagnosisBody, buildDeviceDiagnosis(item));
}

function clearDeviceReport() {
  state.selectedDeviceName = null;
  if (elements.deviceSearchInput) elements.deviceSearchInput.value = "";
  if (elements.deviceReport) elements.deviceReport.hidden = true;
  if (elements.applyDeviceSearch) elements.applyDeviceSearch.disabled = true;
  if (elements.deviceDiagnosisBody) elements.deviceDiagnosisBody.replaceChildren();
}

function openDeviceTab() {
  const tab = document.getElementById("tab-device");
  if (!tab || tab.disabled) return;
  clearDeviceReport();
  renderDeviceSearch();
  activateTab(tab);
  document.getElementById("panel-device")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function applyDeviceSearch() {
  const item = findDevice(elements.deviceSearchInput.value.trim());
  if (!item) {
    elements.applyDeviceSearch.disabled = true;
    return;
  }
  state.selectedDeviceName = item.name;
  renderDeviceReport(item);
  elements.deviceReport.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function backToFirmOverview() {
  const tab = document.getElementById("tab-overview");
  if (tab) activateTab(tab);
  elements.conclusionCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function syncDeviceTabAvailability() {
  const tab = document.getElementById("tab-device");
  if (!tab) return;
  const blocked = isSuppressedProfile();
  tab.disabled = blocked;
  tab.classList.toggle("is-disabled", blocked);
  if (blocked && tab.getAttribute("aria-selected") === "true") {
    activateTab(document.getElementById("tab-overview"));
  }
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
  syncDeviceTabAvailability();
  if (isSuppressedProfile()) {
    clearDeviceReport();
    updateFlowSteps();
    return;
  }
  renderMetrics();
  renderTrendChart();
  renderOpportunityChart();
  renderOpportunityTable();
  renderSimilarGroups();
  renderQuestions();
  renderDeviceSearch();
  updateFlowSteps();
}

function activateTab(tab) {
  if (!tab || tab.disabled) return;
  elements.tabs.forEach((candidate) => {
    const selected = candidate === tab;
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  elements.panels.forEach((panel) => {
    panel.hidden = panel.id !== tab.getAttribute("aria-controls");
  });
  if (tab.id === "tab-device") {
    renderDeviceSearch();
  }
  updateFlowSteps();
}

function bindTabs() {
  elements.tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const enabled = elements.tabs.filter((candidate) => !candidate.disabled);
      if (!enabled.length) return;
      let nextIndex = enabled.indexOf(tab);
      if (nextIndex < 0) nextIndex = 0;
      if (event.key === "ArrowLeft") nextIndex = (nextIndex - 1 + enabled.length) % enabled.length;
      if (event.key === "ArrowRight") nextIndex = (nextIndex + 1) % enabled.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = enabled.length - 1;
      activateTab(enabled[nextIndex]);
      enabled[nextIndex].focus();
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
    state.selectedDeviceName = null;
    clearDeviceReport();
    renderAll();
    activateTab(document.getElementById("tab-overview"));
    elements.conclusionCard?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  elements.openDeviceTab?.addEventListener("click", openDeviceTab);
  elements.applyDeviceSearch?.addEventListener("click", applyDeviceSearch);
  elements.backToFirmFromDevice?.addEventListener("click", backToFirmOverview);
  elements.backToFirmFromDeviceReport?.addEventListener("click", backToFirmOverview);
  elements.searchAnotherDevice?.addEventListener("click", () => {
    clearDeviceReport();
    renderDeviceSearch();
    elements.deviceSearchInput?.focus();
  });
  elements.deviceSearchInput?.addEventListener("input", () => {
    const match = findDevice(elements.deviceSearchInput.value.trim());
    state.selectedDeviceName = match ? match.name : null;
    elements.applyDeviceSearch.disabled = !match;
  });
  [elements.businessType, elements.region, elements.productGroup].forEach((field) => {
    field.addEventListener("focus", () => {
      state.profileApplied = false;
      updateProfileSteps();
      syncDeviceTabAvailability();
    });
    field.addEventListener("change", () => {
      state.profileApplied = false;
      updateProfileSteps();
      syncDeviceTabAvailability();
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
