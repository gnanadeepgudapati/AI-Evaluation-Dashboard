/**
 * dashboard_charts.js
 * Chart.js visualisations and API interactions for the AI Evaluation Dashboard.
 */

const API_BASE = "";           // same origin
let averagesChart = null;
let historyChart = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreClass(score) {
  if (score >= 0.7) return "score-high";
  if (score >= 0.4) return "score-medium";
  return "score-low";
}

function pct(score) {
  return (score * 100).toFixed(1) + "%";
}

function showError(msg) {
  const el = document.getElementById("error-msg");
  el.textContent = msg;
  el.style.display = msg ? "block" : "none";
}

// ---------------------------------------------------------------------------
// Evaluation form
// ---------------------------------------------------------------------------

async function runEvaluation() {
  const question = document.getElementById("question").value.trim();
  const response = document.getElementById("ai-response").value.trim();
  const context  = document.getElementById("context").value.trim();

  showError("");
  if (!question) { showError("Please enter a question."); return; }
  if (!response) { showError("Please enter an AI response."); return; }

  const btn = document.getElementById("evaluate-btn");
  btn.disabled = true;
  btn.textContent = "Evaluating…";

  try {
    const res = await fetch(`${API_BASE}/api/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, response, context }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Server error");
    }
    const data = await res.json();
    renderResults(data);
    loadHistory();
    loadAverages();
  } catch (e) {
    showError("Error: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Evaluate";
  }
}

function renderResults(data) {
  document.getElementById("results-placeholder").style.display = "none";
  document.getElementById("results-content").style.display = "block";

  const metrics = ["groundedness", "relevance", "safety", "completeness"];
  const container = document.getElementById("metric-cards");
  container.innerHTML = "";

  metrics.forEach((m) => {
    const metric = data[m];
    const cls = scoreClass(metric.score);
    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML = `
      <div class="metric-name">${m}</div>
      <div class="metric-score ${cls}">${pct(metric.score)}</div>
      <div class="metric-level ${cls}">${metric.level.toUpperCase()}</div>
      <div class="metric-reason">${metric.reasoning}</div>
    `;
    container.appendChild(card);
  });

  const badge = document.getElementById("overall-badge");
  badge.textContent = "Overall: " + pct(data.overall_score);
  badge.className = "overall-badge " + scoreClass(data.overall_score);
}

// ---------------------------------------------------------------------------
// History table
// ---------------------------------------------------------------------------

async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/history?limit=50`);
    const rows = await res.json();
    renderHistoryTable(rows);
    try { renderHistoryChart(rows.slice(0, 10).reverse()); } catch (_) { /* chart optional */ }
  } catch (e) {
    document.getElementById("history-container").innerHTML =
      `<p class="empty-state">Could not load history.</p>`;
  }
}

function renderHistoryTable(rows) {
  const container = document.getElementById("history-container");
  if (!rows.length) {
    container.innerHTML = `<p class="empty-state">No evaluations yet.</p>`;
    return;
  }
  const cols = ["id", "created_at", "question", "overall_score",
                "groundedness_score", "relevance_score", "safety_score", "completeness_score"];
  const headers = cols.map((c) => `<th>${c.replace(/_/g, " ")}</th>`).join("");
  const bodyRows = rows.map((r) => {
    return `<tr>${cols.map((c) => {
      const v = r[c];
      if (c === "question") return `<td title="${v}">${v.length > 40 ? v.slice(0, 40) + "…" : v}</td>`;
      if (c === "created_at") return `<td>${new Date(v).toLocaleString()}</td>`;
      if (typeof v === "number" && c !== "id")
        return `<td class="${scoreClass(v)}">${pct(v)}</td>`;
      return `<td>${v}</td>`;
    }).join("")}</tr>`;
  }).join("");
  container.innerHTML = `
    <table class="history-table">
      <thead><tr>${headers}</tr></thead>
      <tbody>${bodyRows}</tbody>
    </table>`;
}

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

async function loadAverages() {
  try {
    const res = await fetch(`${API_BASE}/api/metrics/averages`);
    const data = await res.json();
    renderAveragesChart(data);
  } catch (_) { /* silent */ }
}

function renderAveragesChart(data) {
  if (typeof Chart === "undefined") return;
  const labels = ["Groundedness", "Relevance", "Safety", "Completeness"];
  const values = [data.groundedness, data.relevance, data.safety, data.completeness];
  const colors = ["#667eea", "#48bb78", "#ed8936", "#e53e3e"];

  const ctx = document.getElementById("averages-chart").getContext("2d");
  if (averagesChart) averagesChart.destroy();
  averagesChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Average Score",
        data: values,
        backgroundColor: colors,
        borderRadius: 6,
      }],
    },
    options: {
      scales: { y: { min: 0, max: 1, ticks: { callback: (v) => pct(v) } } },
      plugins: { legend: { display: false } },
    },
  });
}

function renderHistoryChart(rows) {
  if (typeof Chart === "undefined") return;
  const labels = rows.map((r) => "#" + r.id);
  const values = rows.map((r) => r.overall_score);

  const ctx = document.getElementById("history-chart").getContext("2d");
  if (historyChart) historyChart.destroy();
  historyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Overall Score",
        data: values,
        borderColor: "#667eea",
        backgroundColor: "rgba(102,126,234,0.15)",
        tension: 0.3,
        fill: true,
        pointRadius: 4,
      }],
    },
    options: {
      scales: { y: { min: 0, max: 1, ticks: { callback: (v) => pct(v) } } },
      plugins: { legend: { display: false } },
    },
  });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  loadHistory();
  loadAverages();
});
