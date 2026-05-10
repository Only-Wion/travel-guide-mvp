const state = {
  response: null,
  demos: [],
  importResult: null,
};

const form = document.getElementById("planner-form");
const formStatus = document.getElementById("form-status");
const resultsGrid = document.getElementById("results-grid");
const riskPanels = document.getElementById("risk-panels");
const executionCard = document.getElementById("execution-card");
const importStatus = document.getElementById("import-status");
const importResults = document.getElementById("import-results");
const xiaohongshuUrlInput = document.getElementById("xiaohongshu-url");
const noteTextInput = document.getElementById("note-text");
const desiredPlacesInput = document.getElementById("desired-places");

function switchView(viewName) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${viewName}`);
  });
  // Re-trigger entrance animation
  const activeView = document.getElementById(`view-${viewName}`);
  if (activeView) {
    activeView.style.animation = "none";
    activeView.offsetHeight;
    activeView.style.animation = "";
  }
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderDemoCases() {
  const container = document.getElementById("demo-cases");
  container.innerHTML = "";
  state.demos.forEach((item) => {
    const card = document.createElement("div");
    card.className = "demo-card";
    card.innerHTML = `
      <h4>${item.title}</h4>
      <p>${item.origin_city} → ${item.destination_city}</p>
      <p>预算 ¥${item.budget_cny} / ${item.travelers} 人</p>
      <button class="btn btn-secondary" data-demo-id="${item.id}">加载这个案例</button>
    `;
    container.appendChild(card);
  });
}

function fillForm(data) {
  Object.entries(data).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === "checkbox") {
      field.checked = Boolean(value);
      return;
    }
    field.value = Array.isArray(value) ? value.join(",") : value;
  });
}

function collectPayload() {
  const payload = Object.fromEntries(new FormData(form).entries());
  const rawPlaces = desiredPlacesInput.value.trim();
  const desiredPlaces = rawPlaces
    ? rawPlaces
        .split(/[\n,]+/)
        .map((item) => item.trim())
        .filter(Boolean)
    : [];
  return {
    origin_city: payload.origin_city.trim(),
    destination_city: payload.destination_city.trim(),
    departure_date: payload.departure_date,
    return_date: payload.return_date,
    budget_cny: Number(payload.budget_cny),
    preference_mode: payload.preference_mode,
    allow_night_arrival: form.elements.namedItem("allow_night_arrival").checked,
    min_transfer_buffer_minutes: Number(payload.min_transfer_buffer_minutes),
    travelers: Number(payload.travelers),
    preferences: payload.preferences
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    desired_places: desiredPlaces,
  };
}

function getDesiredPlacesList() {
  const rawText = desiredPlacesInput.value.trim();
  return rawText
    ? rawText.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean)
    : [];
}

function isPlaceInDesired(placeName) {
  return getDesiredPlacesList().includes(placeName);
}

function addToDesiredPlaces(placeName) {
  const desired = getDesiredPlacesList();
  if (!desired.includes(placeName)) {
    desired.push(placeName);
    desiredPlacesInput.value = desired.join("\n");
    updateImportResultsButtons();
  }
}

function removeFromDesiredPlaces(placeName) {
  const desired = getDesiredPlacesList().filter((item) => item !== placeName);
  desiredPlacesInput.value = desired.length ? desired.join("\n") : "";
  updateImportResultsButtons();
}

function updateImportResultsButtons() {
  // 更新所有导入结果中的地点/餐厅按钮状态
  document.querySelectorAll("[data-place-item]").forEach((item) => {
    const placeName = item.dataset.placeItem;
    const isInDesired = isPlaceInDesired(placeName);
    
    const addBtn = item.querySelector(".add-to-desired-btn");
    const removeBtn = item.querySelector(".remove-from-desired-btn");
    
    if (addBtn) {
      addBtn.disabled = isInDesired;
      addBtn.style.opacity = isInDesired ? "0.5" : "1";
    }
    if (removeBtn) {
      removeBtn.disabled = !isInDesired;
      removeBtn.style.opacity = !isInDesired ? "0.5" : "1";
    }
  });
}

function renderImportResults() {
  if (!state.importResult) {
    importResults.className = "import-results empty";
    importResults.textContent = "解析结果会显示在这里，支持手动粘贴文本，或仅填写小红书链接。";
    return;
  }

  const { locations, restaurants, restaurant_details: details, risk_tips: riskTips, source_url: sourceUrl } = state.importResult;
  const sourceLabel =
    state.importResult.source_type === "xiaohongshu_link" ? "链接导入" : "手动导入";

  const detailMap = {};
  if (details) {
    details.forEach((d) => { detailMap[d.name] = d; });
  }

  function renderLocationItem(location) {
    const isInDesired = isPlaceInDesired(location);
    return `
      <div class="import-place-item" data-place-item="${location}">
        <span class="place-name">${location}</span>
        <div class="place-buttons">
          <button type="button" class="btn btn-small add-to-desired-btn" 
            ${isInDesired ? "disabled" : ""}
            style="${isInDesired ? "opacity: 0.5;" : ""}">➕ 加入</button>
          <button type="button" class="btn btn-small remove-from-desired-btn" 
            ${!isInDesired ? "disabled" : ""}
            style="${!isInDesired ? "opacity: 0.5;" : ""}">➖ 删除</button>
        </div>
      </div>
    `;
  }

  function renderRestaurantItem(name) {
    const d = detailMap[name];
    const isInDesired = isPlaceInDesired(name);
    
    let detailHtml = "";
    if (d) {
      let lines = [`<strong>${d.name}</strong>`];
      if (d.rating) lines.push(`⭐ ${d.rating}`);
      if (d.avg_price) lines.push(`人均 ${d.avg_price}`);
      if (d.phone) lines.push(`☎ ${d.phone}`);
      if (d.address) lines.push(`${d.address}`);
      let links = [];
      if (d.meituan_url) links.push(`<a href="${d.meituan_url}" target="_blank" rel="noopener">美团</a>`);
      if (d.dianping_url) links.push(`<a href="${d.dianping_url}" target="_blank" rel="noopener">点评</a>`);
      if (links.length) lines.push(links.join(" · "));
      if (d.queue_tip) lines.push(`⚠ ${d.queue_tip}`);
      detailHtml = `<div class="restaurant-detail">${lines.join("<br>")}</div>`;
    }

    return `
      <div class="import-place-item restaurant-item" data-place-item="${name}">
        <div class="place-header">
          <span class="place-name">${name}</span>
          <div class="place-buttons">
            <button type="button" class="btn btn-small add-to-desired-btn" 
              ${isInDesired ? "disabled" : ""}
              style="${isInDesired ? "opacity: 0.5;" : ""}">➕ 加入</button>
            <button type="button" class="btn btn-small remove-from-desired-btn" 
              ${!isInDesired ? "disabled" : ""}
              style="${!isInDesired ? "opacity: 0.5;" : ""}">➖ 删除</button>
          </div>
        </div>
        ${detailHtml}
      </div>
    `;
  }

  importResults.className = "import-results";
  importResults.innerHTML = `
    <div class="import-summary">
      <span class="pill pill-blue">${sourceLabel}</span>
      <strong>${locations.length}</strong> 个地点
      <strong>${restaurants.length}</strong> 家餐厅
      <strong>${riskTips.length}</strong> 条风险提示
      ${sourceUrl ? `<small class="text-small">来源链接：${sourceUrl}</small>` : '<small class="text-small">未填写来源链接</small>'}
    </div>
    <div class="import-grid result-grid">
      <article class="import-card">
        <h4>地点</h4>
        <div class="place-list">${
          locations.length
            ? locations.map(renderLocationItem).join("")
            : '<div class="import-place-item">未识别到明确地点</div>'
        }</div>
      </article>
      <article class="import-card">
        <h4>餐厅 (含高德搜索)</h4>
        <div class="place-list">${
          restaurants.length
            ? restaurants.map(renderRestaurantItem).join("")
            : '<div class="import-place-item">未识别到明确餐厅</div>'
        }</div>
      </article>
      <article class="import-card full">
        <h4>风险提示</h4>
        <ul>${
          riskTips.length
            ? riskTips
                .map(
                  (item) =>
                    `<li><strong>${item.level.toUpperCase()}</strong> · ${item.content}</li>`
                )
                .join("")
            : "<li>未识别到明确风险提示</li>"
        }</ul>
      </article>
    </div>
  `;

  // 绑定按钮事件
  document.querySelectorAll(".add-to-desired-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const placeName = btn.closest("[data-place-item]").dataset.placeItem;
      addToDesiredPlaces(placeName);
    });
  });

  document.querySelectorAll(".remove-from-desired-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const placeName = btn.closest("[data-place-item]").dataset.placeItem;
      removeFromDesiredPlaces(placeName);
    });
  });
}

function renderResults() {
  if (!state.response) return;
  resultsGrid.innerHTML = state.response.plans
    .map(
      (plan) => `
      <article class="card">
        <div class="plan-card-body">
          <div class="plan-header">
            <div class="plan-header-left">
              <span class="pill pill-blue">${plan.label}</span>
              <h3>${plan.positioning}</h3>
            </div>
            <div class="plan-header-right">${plan.metrics.confidence_score} / 100<br />可信度</div>
          </div>
          <p class="plan-summary">${plan.summary}</p>
          <div class="metric-grid">
            <div class="metric">
              总成本
              <strong>¥${plan.metrics.total_cost_cny}</strong>
            </div>
            <div class="metric">
              风险分
              <strong>${plan.metrics.risk_score}</strong>
            </div>
          </div>
          <div class="source-list">
            ${(plan.route_segments || [])
              .map(
                (segment) => `
                  <div class="source-item">
                    <strong>${segment.leg_title}</strong>
                    <div>${segment.depart_at} 路 ${segment.arrive_at}</div>
                    <small class="text-small">${segment.summary}</small>
                  </div>
                `
              )
              .join("")}
          </div>
          <div class="daily-list">
            ${(plan.daily_stops || [])
              .map(
                (stop) => `
                  <div class="daily-item">
                    <strong>Day ${stop.day} ${stop.time_range} · ${stop.title}</strong>
                    <div>${stop.highlight}</div>
                  </div>
                `
              )
              .join("")}
          </div>
          <div class="source-list">
            ${(plan.source_references || [])
              .map(
                (source) => `
                  <div class="source-item">
                    <strong>${source.title}</strong>
                    <div>${source.source} · 可信度 ${Math.round(source.confidence * 100)}%</div>
                    <small class="text-small">${source.updated_at}</small>
                  </div>
                `
              )
              .join("")}
          </div>
        </div>
      </article>
    `
    )
    .join("");
}

function renderRisks() {
  if (!state.response) return;
  riskPanels.innerHTML = state.response.plans
    .map(
      (plan) => `
      <article class="card">
        <div class="plan-card-body">
          <div class="plan-header">
            <div class="plan-header-left">
              <span class="pill pill-blue">${plan.label}</span>
              <h3>${plan.why_this_plan}</h3>
            </div>
          </div>
          <p class="plan-summary">${plan.decision_hint}</p>
          <div class="risk-list">
            ${plan.risks
              .map(
                (risk) => `
                  <div class="risk-item ${risk.level}">
                    <strong>${risk.level.toUpperCase()} · ${risk.title}</strong>
                    <p>${risk.description}</p>
                    <small>用户取舍：${risk.user_tradeoff}</small>
                  </div>
                `
              )
              .join("")}
          </div>
        </div>
      </article>
    `
    )
    .join("");
}

function renderCard() {
  if (!state.response) return;
  const card = state.response.execution_card;
  executionCard.className = "card execution-card-body";
  executionCard.innerHTML = `
    <h3>${card.title}</h3>
    <p><strong>时间窗口：</strong>${card.trip_window}</p>
    <p><strong>同行摘要：</strong>${card.traveler_summary}</p>
    <div class="card-block">
      <h4>关键行程</h4>
      <ul>${card.day_brief.map((item) => `<li>${item}</li>`).join("")}</ul>
    </div>
    <div class="card-block">
      <h4>风险提醒</h4>
      <ul>${card.risk_brief.map((item) => `<li>${item}</li>`).join("")}</ul>
    </div>
    <div class="card-block">
      <h4>出发前检查</h4>
      <ul>${card.final_checklist.map((item) => `<li>${item}</li>`).join("")}</ul>
    </div>
  `;
}

async function generatePlan(event) {
  event.preventDefault();
  formStatus.textContent = "正在生成两套方案...";
  try {
    const response = await fetch("/api/v1/plans/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectPayload()),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "生成失败");
    }
    state.response = data;
    renderResults();
    renderRisks();
    renderCard();
    formStatus.textContent = "生成完成，可以依次查看结果页、风险解释页和执行卡页。";
    switchView("results");
  } catch (error) {
    formStatus.textContent = error.message || "生成失败";
  }
}

async function importSource() {
  const sourceUrl = xiaohongshuUrlInput.value.trim();
  const noteText = noteTextInput.value.trim();
  if (!noteText && !sourceUrl) {
    importStatus.textContent = "请先填写小红书链接或粘贴笔记文本";
    state.importResult = null;
    renderImportResults();
    return;
  }

  importStatus.textContent = noteText
    ? "正在解析笔记文本中的地点、餐厅和风险提示..."
    : "正在读取链接并解析内容...";
  try {
    const response = await fetch("/api/v1/sources/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        xiaohongshu_url: sourceUrl,
        note_text: noteText,
        destination_city: (form.elements.namedItem("destination_city")?.value || "").trim() || null,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "导入失败");
    }
    state.importResult = data;
    renderImportResults();
    importStatus.textContent = "解析完成，可以继续生成旅行方案。";
  } catch (error) {
    importStatus.textContent = error.message || "导入失败";
  }
}

async function loadDemoCases() {
  const response = await fetch("/api/v1/demo-cases");
  const data = await response.json();
  state.demos = data.cases || [];
  renderDemoCases();
}

document.querySelectorAll(".nav-link").forEach((button) => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});

document.getElementById("load-default").addEventListener("click", () => {
  if (state.demos[0]) fillForm(state.demos[0]);
});

document.getElementById("reload-demos").addEventListener("click", loadDemoCases);
document.getElementById("import-source").addEventListener("click", importSource);

document.getElementById("demo-cases").addEventListener("click", (event) => {
  const target = event.target.closest("[data-demo-id]");
  if (!target) return;
  const demo = state.demos.find((item) => item.id === target.dataset.demoId);
  if (demo) {
    fillForm(demo);
    switchView("input");
  }
});

document.getElementById("copy-card").addEventListener("click", async () => {
  if (!state.response) return;
  await navigator.clipboard.writeText(state.response.execution_card.text_version);
});

document.getElementById("print-card").addEventListener("click", () => {
  if (!state.response) return;
  const popup = window.open("", "_blank");
  popup.document.write(`
    <html>
      <head><title>执行卡</title><style>body{font-family:-apple-system,sans-serif;padding:24px;line-height:1.6;color:#1d1d1f}</style></head>
      <body>${state.response.execution_card.html_version}</body>
    </html>
  `);
  popup.document.close();
  popup.print();
});

form.addEventListener("submit", generatePlan);

// 监听"想去的地方"的变化，实时更新导入结果中的按钮状态
desiredPlacesInput.addEventListener("input", updateImportResultsButtons);

renderImportResults();
loadDemoCases();
