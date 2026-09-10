// ---------------------------------------------------------------------------
// CodeLingo frontend â€” no framework, just fetch() + DOM + the Web Speech API.
// ---------------------------------------------------------------------------

const state = {
  lastLines: [],        // most recent /api/explain result
  practiceUnits: [],     // [{explanation, code}], built from lastLines
  practiceIndex: 0,
  xp: Number(localStorage.getItem("codelingo_xp") || 0),
  streak: Number(localStorage.getItem("codelingo_streak") || 0),
};

const $ = (sel) => document.querySelector(sel);

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    tab.classList.add("active");
    tab.setAttribute("aria-selected", "true");
    document.querySelectorAll(".tab").forEach((t) => { if (t !== tab) t.setAttribute("aria-selected", "false"); });
    $(`#view-${tab.dataset.view}`).classList.add("active");
  });
});

function goToTab(view) {
  document.querySelector(`.tab[data-view="${view}"]`).click();
}

// ---------------------------------------------------------------------------
// XP / streak
// ---------------------------------------------------------------------------
function renderXp() {
  $("#xpValue").textContent = state.xp;
  $("#streakValue").textContent = state.streak;
}
function awardXp(amount, keepStreak) {
  state.xp += amount;
  state.streak = keepStreak ? state.streak + 1 : 0;
  localStorage.setItem("codelingo_xp", state.xp);
  localStorage.setItem("codelingo_streak", state.streak);
  renderXp();
}
renderXp();

// ---------------------------------------------------------------------------
// Samples
// ---------------------------------------------------------------------------
let SAMPLES = {};
fetch("/api/samples").then((r) => r.json()).then((data) => { SAMPLES = data; });

document.querySelectorAll("[data-sample]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!SAMPLES[btn.dataset.sample]) {
      const data = await fetch("/api/samples").then((r) => r.json());
      SAMPLES = data;
    }
    const sample = SAMPLES[btn.dataset.sample];
    $("#codeInput").value = sample.code;
    goToTab("explain");
    await explainCode();
  });
});

// ---------------------------------------------------------------------------
// Explain view
// ---------------------------------------------------------------------------
$("#explainBtn").addEventListener("click", explainCode);

async function explainCode() {
  const code = $("#codeInput").value;
  if (!code.trim()) return;

  const res = await fetch("/api/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  const data = await res.json();
  state.lastLines = data.lines;
  renderLines(data.lines);
  $("#explainToolbar").hidden = false;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// turn `backtick code` into <code class="inline">code</code> for readability
function formatExplanation(text) {
  return escapeHtml(text).replace(/`([^`]+)`/g, '<code class="inline">$1</code>');
}

function renderLines(lines) {
  const container = $("#linesOutput");
  container.innerHTML = "";

  lines.forEach((line, idx) => {
    const row = document.createElement("div");
    row.className = `iline kind-${line.kind}`;
    row.dataset.idx = idx;

    if (line.kind === "blank") {
      row.innerHTML = `<div class="gutter">${line.line}</div><div></div>`;
      container.appendChild(row);
      return;
    }

    const indentPx = (line.indent || 0) * 18;
    row.innerHTML = `
      <div class="gutter">${line.line}</div>
      <div>
        <div class="code" style="padding-left:${indentPx}px">${escapeHtml(line.code.trim())}</div>
        <div class="translation" style="padding-left:${indentPx}px">
          <span class="glyph">â†³</span>
          <span class="text">${formatExplanation(line.explanation)}</span>
          <button class="speak" title="Read this line aloud" data-idx="${idx}">ðŸ”Š</button>
        </div>
      </div>`;
    container.appendChild(row);
  });

  container.querySelectorAll(".speak").forEach((btn) => {
    btn.addEventListener("click", () => {
      const i = Number(btn.dataset.idx);
      speak(lines[i].explanation, () => highlightRow(i, true), () => highlightRow(i, false));
    });
  });
}

function highlightRow(idx, on) {
  const row = $(`.iline[data-idx="${idx}"]`);
  if (row) row.classList.toggle("speaking", on);
}

// ---------------------------------------------------------------------------
// Voice layer (Web Speech API â€” runs entirely in the browser)
// ---------------------------------------------------------------------------
let currentUtterance = null;

function speak(text, onStart, onEnd) {
  if (!("speechSynthesis" in window)) {
    alert("This browser doesn't support speech synthesis. Try Chrome, Edge, or Safari.");
    return;
  }
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text.replace(/`/g, ""));
  utter.rate = 1.0;
  utter.pitch = 1.0;
  if (onStart) utter.onstart = onStart;
  if (onEnd) utter.onend = onEnd;
  currentUtterance = utter;
  window.speechSynthesis.speak(utter);
}

function speakSequence(items, onEachStart, onEachEnd, onDone) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  let i = 0;
  function next() {
    if (i >= items.length) { onDone && onDone(); return; }
    const { text, idx } = items[i];
    const utter = new SpeechSynthesisUtterance(text.replace(/`/g, ""));
    utter.onstart = () => onEachStart && onEachStart(idx);
    utter.onend = () => { onEachEnd && onEachEnd(idx); i += 1; next(); };
    window.speechSynthesis.speak(utter);
  }
  next();
}

$("#readAllBtn").addEventListener("click", () => {
  const items = state.lastLines
    .map((l, idx) => ({ text: l.explanation, idx }))
    .filter((x) => x.text);
  if (!items.length) return;

  $("#readAllBtn").hidden = true;
  $("#stopReadBtn").hidden = false;

  speakSequence(
    items,
    (idx) => highlightRow(idx, true),
    (idx) => highlightRow(idx, false),
    () => { $("#readAllBtn").hidden = false; $("#stopReadBtn").hidden = true; }
  );
});

$("#stopReadBtn").addEventListener("click", () => {
  window.speechSynthesis.cancel();
  document.querySelectorAll(".iline.speaking").forEach((el) => el.classList.remove("speaking"));
  $("#readAllBtn").hidden = false;
  $("#stopReadBtn").hidden = true;
});

// ---------------------------------------------------------------------------
// Practice view
// ---------------------------------------------------------------------------
const SKIP_KINDS = new Set(["blank", "comment"]);

$("#toPracticeBtn").addEventListener("click", () => {
  buildPracticeSet(state.lastLines);
  goToTab("practice");
});

function buildPracticeSet(lines) {
  state.practiceUnits = lines
    .filter((l) => !SKIP_KINDS.has(l.kind) && l.explanation)
    .map((l) => ({ explanation: l.explanation, code: l.code.trim() }));
  state.practiceIndex = 0;
  showPracticeUnit();
}

function showPracticeUnit() {
  const units = state.practiceUnits;
  if (!units.length) {
    $("#practiceEmpty").hidden = false;
    $("#practiceCardWrap").hidden = true;
    return;
  }
  $("#practiceEmpty").hidden = true;
  $("#practiceCardWrap").hidden = false;

  const idx = state.practiceIndex;
  const unit = units[idx];

  $("#progressCurrent").textContent = idx + 1;
  $("#progressTotal").textContent = units.length;
  $("#progressFill").style.width = `${((idx) / units.length) * 100}%`;

  $("#practiceExplanation").innerHTML = formatExplanation(unit.explanation);
  $("#practiceInput").value = "";
  $("#practiceInput").focus();
  $("#feedback").hidden = true;
  $("#answerReveal").hidden = true;
  $("#nextBtn").hidden = true;
  $("#checkBtn").hidden = false;
}

$("#speakCardBtn").addEventListener("click", () => {
  const unit = state.practiceUnits[state.practiceIndex];
  if (unit) speak(unit.explanation);
});

$("#revealBtn").addEventListener("click", () => {
  const unit = state.practiceUnits[state.practiceIndex];
  const box = $("#answerReveal");
  box.textContent = unit.code;
  box.hidden = false;
});

$("#checkBtn").addEventListener("click", async () => {
  const unit = state.practiceUnits[state.practiceIndex];
  const submitted = $("#practiceInput").value;

  const res = await fetch("/api/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected: unit.code, submitted }),
  });
  const result = await res.json();

  const fb = $("#feedback");
  fb.hidden = false;
  fb.classList.toggle("wrong", !result.correct);
  fb.textContent = `${result.hint} (similarity: ${Math.round(result.ratio * 100)}%)`;

  awardXp(result.correct ? 10 : 2, result.correct);

  $("#checkBtn").hidden = true;
  $("#nextBtn").hidden = false;
});

$("#skipBtn").addEventListener("click", () => advancePractice());
$("#nextBtn").addEventListener("click", () => advancePractice());

function advancePractice() {
  if (state.practiceIndex < state.practiceUnits.length - 1) {
    state.practiceIndex += 1;
    showPracticeUnit();
  } else {
    $("#progressFill").style.width = "100%";
    $("#practiceCardWrap").hidden = true;
    $("#practiceEmpty").hidden = false;
    $("#practiceEmpty").innerHTML =
      `<p>Set complete â€” nice work.</p><p class="muted">${state.xp} XP total, ${state.streak} in a row right now.</p>
       <div class="sample-links">
         <button class="btn-link" data-sample="django_search">Django search view</button>
         <button class="btn-link" data-sample="list_comprehension">List comprehension</button>
       </div>`;
    document.querySelectorAll("#practiceEmpty [data-sample]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const sample = SAMPLES[btn.dataset.sample];
        $("#codeInput").value = sample.code;
        goToTab("explain");
        await explainCode();
      });
    });
  }
}

// ---------------------------------------------------------------------------
// Build view â€” goal -> English curriculum -> learner writes the code
// ---------------------------------------------------------------------------
let CHALLENGES = {};
const buildState = { steps: [], verified: [] };

fetch("/api/challenges").then((r) => r.json()).then((data) => { CHALLENGES = data; });

async function loadGoal(goalText) {
  $("#goalMiss").hidden = true;
  const res = await fetch("/api/match-goal", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal: goalText }),
  });
  const result = await res.json();

  if (!result.matched) {
    $("#buildWrap").hidden = true;
    const miss = $("#goalMiss");
    miss.hidden = false;
    miss.innerHTML = `No built-in tutorial for that yet. Try one of the goals above â€” or see the README's "extend first" notes for wiring this up to an LLM so it can handle any goal.`;
    return;
  }

  const challenge = CHALLENGES[result.id];
  buildState.steps = challenge.steps;
  buildState.verified = challenge.steps.map(() => null); // null | true | false

  $("#buildTitle").textContent = challenge.title;
  $("#buildWrap").hidden = false;
  renderBuildRows();
}

function renderBuildRows() {
  const container = $("#buildRows");
  container.innerHTML = "";

  buildState.steps.forEach((step, idx) => {
    const row = document.createElement("div");
    row.className = "brow";
    row.innerHTML = `
      <div class="brow-instruction">
        <span class="brow-num">${idx + 1}</span>
        <span class="brow-text">${formatExplanation(step.explanation)}</span>
      </div>
      <div class="brow-code">
        <textarea class="brow-input" data-idx="${idx}" spellcheck="false" placeholder="Write the matching line of code..."></textarea>
        <div class="brow-actions">
          <button class="btn-secondary brow-verify" data-idx="${idx}">Verify</button>
          <button class="btn-link brow-reveal" data-idx="${idx}">Show answer</button>
        </div>
        <div class="brow-feedback" data-idx="${idx}" hidden></div>
      </div>`;
    container.appendChild(row);
  });

  container.querySelectorAll(".brow-verify").forEach((btn) => {
    btn.addEventListener("click", () => verifyBuildRow(Number(btn.dataset.idx)));
  });
  container.querySelectorAll(".brow-reveal").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.idx);
      const fb = document.querySelector(`.brow-feedback[data-idx="${idx}"]`);
      fb.hidden = false;
      fb.classList.remove("wrong");
      fb.innerHTML = `<span class="mono-inline">${escapeHtml(buildState.steps[idx].code)}</span>`;
    });
  });

  updateBuildScore();
}

async function verifyBuildRow(idx) {
  const textarea = document.querySelector(`.brow-input[data-idx="${idx}"]`);
  const submitted = textarea.value;
  const expected = buildState.steps[idx].code;

  const res = await fetch("/api/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected, submitted }),
  });
  const result = await res.json();

  const wasUnverified = buildState.verified[idx] === null;
  buildState.verified[idx] = result.correct;

  const fb = document.querySelector(`.brow-feedback[data-idx="${idx}"]`);
  fb.hidden = false;
  fb.classList.toggle("wrong", !result.correct);
  fb.textContent = `${result.correct ? "Pass â€” " : "Not yet â€” "}${result.hint}`;

  if (wasUnverified) awardXp(result.correct ? 10 : 2, result.correct);
  updateBuildScore();
}

function updateBuildScore() {
  const total = buildState.verified.length;
  const passed = buildState.verified.filter((v) => v === true).length;
  $("#buildScore").textContent = `${passed} / ${total} verified`;
}

$("#goalGoBtn").addEventListener("click", () => {
  const goal = $("#goalInput").value.trim();
  if (goal) loadGoal(goal);
});
$("#goalInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#goalGoBtn").click();
});
document.querySelectorAll("[data-goal]").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("#goalInput").value = btn.dataset.goal;
    loadGoal(btn.dataset.goal);
  });
});

// Explain the default sample on first load for a working demo out of the box.
window.addEventListener("DOMContentLoaded", () => {
  explainCode();
});
