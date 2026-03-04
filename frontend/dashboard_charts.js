// dashboard_charts.js
// Handles all the JavaScript logic — API calls, rendering results, history table.
// Talks to the FastAPI backend and updates the DOM with the results.

const API_BASE = "http://127.0.0.1:8000";
let scoreChart = null; // keeps track of the chart instance so we can destroy and redraw it


// ----- PAGE NAVIGATION -----

function showPage(pageName, btn) {
  // Hide all pages and deactivate all nav buttons
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));

  // Show the selected page and activate the clicked button
  document.getElementById(`page-${pageName}`).classList.add("active");
  btn.classList.add("active");

  // If switching to history, load the data automatically
  if (pageName === "history") loadHistory();
}


// ----- EVALUATION SUBMISSION -----

async function runEvaluation() {
  // Grab the values from the three input fields
  const question   = document.getElementById("question").value.trim();
  const context    = document.getElementById("context").value.trim();
  const ai_response = document.getElementById("ai_response").value.trim();

  // Basic validation — don't let empty forms through
  if (!question || !context || !ai_response) {
    showError("All three fields are required before running an evaluation.");
    return;
  }

  // Hide previous results and errors, show the loading spinner
  hideError();
  hideResults();
  showLoading();

  // Disable the button so the user can't spam it while waiting
  const btn = document.querySelector(".submit-btn");
  btn.disabled = true;
  btn.textContent = "Evaluating...";

  try {
    // POST request to our FastAPI backend
    const response = await fetch(`${API_BASE}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, context, ai_response })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Something went wrong.");
    }

    const data = await response.json();
    renderResults(data); // hand the data off to the renderer

  } catch (error) {
    showError(`Error: ${error.message}`);
  } finally {
    // Always re-enable the button whether it succeeded or failed
    hideLoading();
    btn.disabled = false;
    btn.textContent = "Run Evaluation";
  }
}


// ----- RENDER RESULTS -----

function renderResults(data) {
  const metrics = ["groundedness", "relevance", "safety", "completeness"];

  // Fill in each score card
  metrics.forEach(metric => {
    const result = data[metric];
    const score  = result.score;

    document.getElementById(`score-${metric}`).textContent = score.toFixed(2);
    document.getElementById(`reasoning-${metric}`).textContent = result.reasoning;

    // Set the score bar width as a percentage
    setTimeout(() => {
      document.getElementById(`bar-${metric}`).style.width = `${score * 100}%`;
    }, 100); // small delay so the CSS transition actually plays

    // Pass/fail badge
    const badge = document.getElementById(`badge-${metric}`);
    badge.textContent  = result.passed ? "PASS" : "FAIL";
    badge.className    = `card-badge ${result.passed ? "badge-pass" : "badge-fail"}`;
  });

  // Overall score
  const overall = data.overall_score;
  const overallEl = document.getElementById("overall-number");
  overallEl.textContent = overall.toFixed(2);
  overallEl.className   = `overall-number ${overall >= 0.8 ? "high" : overall >= 0.6 ? "mid" : "low"}`;

  // Overall status text
  document.getElementById("overall-status").textContent =
    overall >= 0.8 ? "Strong response" :
    overall >= 0.6 ? "Acceptable — some gaps" :
    "Needs improvement";

  // Draw the chart
  drawChart(data);

  showResults();
}


// ----- CHART -----

function drawChart(data) {
  // Destroy the previous chart instance if one exists
  // Without this, Chart.js throws an error on the second evaluation
  if (scoreChart) {
    scoreChart.destroy();
    scoreChart = null;
  }

  const ctx = document.getElementById("score-chart").getContext("2d");

  scoreChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Groundedness", "Relevance", "Safety", "Completeness"],
      datasets: [{
        label: "Score",
        data: [
          data.groundedness.score,
          data.relevance.score,
          data.safety.score,
          data.completeness.score
        ],
        backgroundColor: [
          "rgba(56, 189, 248, 0.3)",
          "rgba(52, 211, 153, 0.3)",
          "rgba(167, 139, 250, 0.3)",
          "rgba(251, 146, 60, 0.3)"
        ],
        borderColor: [
          "rgba(56, 189, 248, 1)",
          "rgba(52, 211, 153, 1)",
          "rgba(167, 139, 250, 1)",
          "rgba(251, 146, 60, 1)"
        ],
        borderWidth: 2,
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          min: 0,
          max: 1,
          grid: { color: "rgba(255,255,255,0.05)" },
          ticks: {
            color: "#4a5568",
            font: { family: "Space Mono", size: 11 }
          }
        },
        x: {
          grid: { display: false },
          ticks: {
            color: "#4a5568",
            font: { family: "Space Mono", size: 11 }
          }
        }
      }
    }
  });
}


// ----- HISTORY -----

async function loadHistory() {
  try {
    const response = await fetch(`${API_BASE}/evaluations`);
    const data     = await response.json();

    const tbody = document.getElementById("history-body");

    // If no evaluations yet, show empty state
    if (!data.evaluations || data.evaluations.length === 0) {
      tbody.innerHTML = `
        <tr><td colspan="6">
          <div class="empty-state">No evaluations yet — run one first.</div>
        </td></tr>`;
      return;
    }

    // Build a row for each evaluation
    tbody.innerHTML = data.evaluations.map(ev => `
      <tr>
        <td class="question-cell" title="${ev.question}">${ev.question}</td>
        <td>${scorePill(ev.groundedness_score)}</td>
        <td>${scorePill(ev.relevance_score)}</td>
        <td>${scorePill(ev.safety_score)}</td>
        <td>${scorePill(ev.completeness_score)}</td>
        <td>${scorePill(ev.overall_score)}</td>
      </tr>
    `).join("");

  } catch (error) {
    document.getElementById("history-body").innerHTML = `
      <tr><td colspan="6">
        <div class="empty-state">Could not load history — is the server running?</div>
      </td></tr>`;
  }
}


// Returns a colored pill based on the score value
function scorePill(score) {
  const cls = score >= 0.8 ? "pill-high" : score >= 0.6 ? "pill-mid" : "pill-low";
  return `<span class="score-pill ${cls}">${score.toFixed(2)}</span>`;
}


// ----- UI HELPERS -----

function showLoading()  { document.getElementById("loading").classList.add("visible"); }
function hideLoading()  { document.getElementById("loading").classList.remove("visible"); }
function showResults()  { document.getElementById("results").classList.add("visible"); }
function hideResults()  { document.getElementById("results").classList.remove("visible"); }
function showError(msg) {
  const el = document.getElementById("error-msg");
  el.textContent = msg;
  el.classList.add("visible");
}
function hideError() { document.getElementById("error-msg").classList.remove("visible"); }