/*
 * quiz.js
 * =======
 * Abstract:
 *   All client-side logic for Cramly's interactive quiz. Manages the four
 *   screens (input, agent, quiz, results) and handles:
 *     - Notes status check on load (GET /api/notes-status)
 *     - SSE connection to stream the AI agent's live decisions
 *     - "Use Notes" mode: passes useNotes=true to the SSE endpoint so the
 *       backend generates from processed notes instead of web searches
 *     - Minimal agent progress view with opt-in detailed log
 *     - Multiple-choice and true/false answer checking
 *     - Short-answer LLM grading via POST /api/evaluate-answer (with
 *       partial-credit score tracking: 0, 0.5, or 1 per question)
 *     - Post-quiz options: harder questions, similar questions, subtopic
 *       deep-dives (re-runs the full agent flow with a new topic)
 *
 * Code Flow:
 *   1. init()                  — wire all static DOM event listeners,
 *                                check notes availability.
 *   2. handleFormSubmit()      — read form (incl. useNotes checkbox),
 *                                go to agent screen, open SSE.
 *   3. triggerQuizGeneration() — shared entry point used by form AND by the
 *                                post-quiz "harder/similar/subtopic" buttons.
 *   4. openAgentStream()       — open EventSource; each event calls
 *                                handleAgentEvent().
 *   5. handleAgentEvent()      — update spinner text + log; on "complete"
 *                                show Start Quiz button.
 *   6. startQuiz()             — store quiz, render quiz screen.
 *   7. renderQuestion()        — dispatch to renderMC / renderTF / renderSA.
 *   8. Short-answer flow:
 *        handleSASubmit()  → callEvaluateAPI()  → showEvaluationResult()
 *   9. showResults()           — score (with partial credit), missed questions,
 *                                post-quiz action buttons, subtopic grid.
 */

"use strict";

/* =========================================================================
   State
   ========================================================================= */
const state = {
  quiz:         null,   // full quiz object from the API
  current:      0,      // current question index
  // answers: [{ correct: bool, score: 0|0.5|1 }] — one entry per question
  answers:      [],
  answered:     false,  // prevents double-clicks before Next is shown
  topic:        "",     // stored so post-quiz options can re-use it
  difficulty:   "Intermediate",
  numQuestions: 10,
  useNotes:     false,  // whether the last quiz was generated from notes
  searchCount:  0       // counts search_start events for the progress display
};


/* =========================================================================
   Screen management
   ========================================================================= */

function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}


/* =========================================================================
   Notes status — checked on page load
   ========================================================================= */

async function checkNotesStatus() {
  const badge = document.getElementById("notes-status-badge");
  const hint  = document.getElementById("notes-hint");
  const box   = document.getElementById("use-notes-checkbox");

  try {
    const res  = await fetch("/api/notes-status");
    const data = await res.json();

    if (data.available) {
      badge.textContent = `${data.chunk_count} chunks ready`;
      badge.className   = "notes-status-badge available";
      hint.textContent  =
        `Your processed notes are ready (${data.chunk_count} chunks from ` +
        `${data.source_count} source${data.source_count !== 1 ? "s" : ""}). ` +
        `The quiz will be generated from your notes instead of web searches.`;
    } else {
      badge.textContent = "no notes";
      badge.className   = "notes-status-badge unavailable";
      box.disabled      = true;
      hint.textContent  =
        "No processed notes found. Process your notes first, then check this box.";
    }
  } catch {
    badge.textContent = "unavailable";
    badge.className   = "notes-status-badge unavailable";
    box.disabled      = true;
  }
}

function handleNotesCheckboxChange() {
  const checked = document.getElementById("use-notes-checkbox").checked;
  const hint    = document.getElementById("notes-hint");
  if (checked) {
    hint.classList.remove("hidden");
  } else {
    hint.classList.add("hidden");
  }
}


/* =========================================================================
   Form submission
   ========================================================================= */

function handleFormSubmit(event) {
  event.preventDefault();
  const topic        = document.getElementById("topic").value.trim();
  const difficulty   = document.getElementById("difficulty").value;
  const numQuestions = parseInt(document.getElementById("num-questions").value, 10);
  const useNotes     = document.getElementById("use-notes-checkbox").checked &&
                       !document.getElementById("use-notes-checkbox").disabled;
  triggerQuizGeneration(topic, difficulty, numQuestions, useNotes);
}


/* =========================================================================
   Central quiz-generation entry point
   =========================================================================
   Called by the form AND by the post-quiz action buttons (harder, similar,
   subtopic). Resets everything and starts a fresh SSE stream.
   ========================================================================= */

function triggerQuizGeneration(topic, difficulty, numQuestions, useNotes = false) {
  state.topic        = topic;
  state.difficulty   = difficulty;
  state.numQuestions = numQuestions;
  state.useNotes     = useNotes;
  state.searchCount  = 0;

  resetAgentScreen(topic, difficulty, useNotes);
  showScreen("agent-screen");
  openAgentStream(topic, difficulty, numQuestions, useNotes);
}

function resetAgentScreen(topic, difficulty, useNotes) {
  const modeLabel = useNotes ? "from your notes on" : "on";
  document.getElementById("agent-topic-label").textContent =
    `Building a ${difficulty.toLowerCase()} quiz ${modeLabel} "${topic}"`;
  document.getElementById("agent-status-text").textContent = "Starting...";
  document.getElementById("search-counter").textContent    = "";

  const spinner = document.getElementById("agent-spinner");
  spinner.classList.remove("spinner-done");

  const initText = useNotes
    ? "Agent started. Analyzing your notes..."
    : "Agent started. Searching the web for resources...";

  document.getElementById("agent-log").innerHTML = `
    <div class="log-entry log-info">
      <span class="log-tag">INIT</span>
      <span class="log-text">${escHtml(initText)}</span>
    </div>`;
  document.getElementById("agent-log-wrap").classList.add("hidden");
  document.getElementById("log-toggle").textContent = "Show Agent Log";

  document.getElementById("reasoning-wrap").classList.add("hidden");
  document.getElementById("reasoning-box").classList.add("hidden");
  document.getElementById("reasoning-summary-toggle").textContent = "Show Agent Reasoning";
  document.getElementById("agent-actions").classList.add("hidden");
}


/* =========================================================================
   SSE — agent decision stream
   ========================================================================= */

function openAgentStream(topic, difficulty, numQuestions, useNotes) {
  const params = new URLSearchParams({ topic, difficulty, numQuestions, useNotes });
  const source = new EventSource(`/api/quiz-stream?${params}`);

  source.onmessage = (e) => {
    const event = JSON.parse(e.data);
    handleAgentEvent(event, source);
  };

  source.onerror = () => {
    source.close();
    document.getElementById("agent-status-text").textContent =
      "Connection lost. Please try again.";
    setTimeout(() => showScreen("input-screen"), 3000);
  };
}

function handleAgentEvent(event, source) {
  switch (event.type) {

    case "notes_loaded":
      document.getElementById("agent-status-text").textContent =
        "Analyzing your notes...";
      document.getElementById("search-counter").textContent = event.message;
      appendLogEntry("info", "NOTES", event.message);
      break;

    case "search_start":
      state.searchCount++;
      document.getElementById("agent-status-text").textContent =
        "Searching for resources...";
      document.getElementById("search-counter").textContent =
        `Search ${state.searchCount} · "${truncate(event.query, 55)}"`;
      appendLogEntry("pending", "SEARCH", `"${event.query}"`);
      break;

    case "search_done": {
      const preview = event.titles.length > 0
        ? ` — "${truncate(event.titles[0], 55)}"`
        : "";
      updateLastLogEntry("done", "FOUND", `${event.count} results${preview}`);
      break;
    }

    case "generating":
      document.getElementById("agent-status-text").textContent = event.message;
      document.getElementById("search-counter").textContent    = "";
      appendLogEntry("info", "GEN", event.message);
      break;

    case "complete":
      source.close();
      appendLogEntry("success", "DONE", "Quiz ready!");

      document.getElementById("agent-spinner").classList.add("spinner-done");
      document.getElementById("agent-status-text").textContent = "Your quiz is ready!";

      if (event.quiz.reasoning) {
        populateReasoningBoxes(event.quiz.reasoning);
        document.getElementById("reasoning-wrap").classList.remove("hidden");
      }

      state.quiz = event.quiz;
      document.getElementById("agent-actions").classList.remove("hidden");
      break;

    case "error":
      source.close();
      appendLogEntry("error", "ERROR", event.message);
      document.getElementById("agent-status-text").textContent =
        "Something went wrong. Returning to input...";
      setTimeout(() => showScreen("input-screen"), 4000);
      break;
  }
}


/* =========================================================================
   Agent log DOM helpers
   ========================================================================= */

function appendLogEntry(statusClass, tag, text) {
  const log = document.getElementById("agent-log");
  const div = document.createElement("div");
  div.className = `log-entry log-${statusClass}`;
  div.innerHTML = `<span class="log-tag">${escHtml(tag)}</span>
                   <span class="log-text">${escHtml(text)}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function updateLastLogEntry(statusClass, tag, text) {
  const log  = document.getElementById("agent-log");
  const last = log.lastElementChild;
  if (!last) return;
  last.className = `log-entry log-${statusClass}`;
  last.innerHTML = `<span class="log-tag">${escHtml(tag)}</span>
                    <span class="log-text">${escHtml(text)}</span>`;
  log.scrollTop = log.scrollHeight;
}

/** Fill in the reasoning sections (agent screen + quiz side panel). */
function populateReasoningBoxes(reasoning) {
  if (!reasoning) return;

  document.getElementById("reasoning-strategy").textContent =
    reasoning.search_strategy || "";
  document.getElementById("reasoning-concepts").innerHTML =
    (reasoning.key_concepts || []).map(c => `<li>${escHtml(c)}</li>`).join("");
  document.getElementById("reasoning-rationale").textContent =
    reasoning.question_rationale || "";

  document.getElementById("side-strategy").textContent =
    reasoning.search_strategy || "";
  document.getElementById("side-concepts").innerHTML =
    (reasoning.key_concepts || []).map(c => `<li>${escHtml(c)}</li>`).join("");
  document.getElementById("side-rationale").textContent =
    reasoning.question_rationale || "";
}


/* =========================================================================
   Quiz screen setup
   ========================================================================= */

function startQuiz(quiz) {
  state.current  = 0;
  state.answers  = [];
  state.answered = false;

  document.getElementById("reasoning-panel").classList.add("hidden");
  document.getElementById("reasoning-toggle").textContent = "Show Agent Reasoning";

  renderSources(quiz.sources || []);
  showScreen("quiz-screen");
  renderQuestion();
}

function renderSources(sources) {
  document.getElementById("sources-list").innerHTML = sources.map(s => `
    <div class="source-item">
      <span class="source-type-badge">${escHtml(s.type || "notes")}</span>
      ${s.url
        ? `<a href="${escHtml(s.url)}" target="_blank" rel="noopener">${escHtml(s.title)}</a>`
        : `<span>${escHtml(s.title)}</span>`
      }
    </div>
  `).join("");
}


/* =========================================================================
   Progress header
   ========================================================================= */

function updateProgress() {
  const total   = state.quiz.questions.length;
  const current = state.current + 1;
  const pct     = Math.round((state.current / total) * 100);

  document.getElementById("question-counter").textContent =
    `Question ${current} of ${total}`;
  document.getElementById("progress-bar").style.width = `${pct}%`;
  updateScoreDisplay();
}

function updateScoreDisplay() {
  const total   = state.answers.reduce((sum, a) => sum + (a?.score ?? 0), 0);
  const display = Number.isInteger(total) ? total : total.toFixed(1);
  document.getElementById("score-counter").textContent = `Score: ${display}`;
}


/* =========================================================================
   Question rendering — dispatcher
   ========================================================================= */

function renderQuestion() {
  updateProgress();
  state.answered = false;

  const q    = state.quiz.questions[state.current];
  const card = document.getElementById("question-card");

  const typeLabel = {
    multiple_choice: "Multiple Choice",
    true_false:      "True / False",
    short_answer:    "Short Answer"
  }[q.type] ?? q.type;

  let bodyHtml = "";
  if      (q.type === "multiple_choice") bodyHtml = buildMCBody(q);
  else if (q.type === "true_false")      bodyHtml = buildTFBody();
  else if (q.type === "short_answer")    bodyHtml = buildSABody();

  card.innerHTML = `
    <div class="q-type-label">${escHtml(typeLabel)}</div>
    <div class="q-text">${escHtml(q.question)}</div>
    ${bodyHtml}
  `;

  if      (q.type === "multiple_choice") attachMCListeners(q);
  else if (q.type === "true_false")      attachTFListeners(q);
  else if (q.type === "short_answer")    attachSAListeners(q);
}


/* =========================================================================
   Multiple choice
   ========================================================================= */

function buildMCBody(q) {
  const opts = Object.entries(q.options || {}).map(([letter, text]) => `
    <button class="option-btn" data-letter="${escHtml(letter)}">
      <span class="option-letter">${escHtml(letter)}</span>
      <span>${escHtml(text)}</span>
    </button>`).join("");
  return `<div class="options-grid">${opts}</div>`;
}

function attachMCListeners(q) {
  document.querySelectorAll(".option-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (state.answered) return;
      state.answered = true;

      const selected  = btn.dataset.letter;
      const isCorrect = selected === q.correct;

      document.querySelectorAll(".option-btn").forEach(b => {
        b.disabled = true;
        if (b.dataset.letter === q.correct) b.classList.add("correct");
        if (b === btn && !isCorrect)        b.classList.add("incorrect");
      });

      recordAnswer(isCorrect, isCorrect ? 1 : 0);
      showExplanation(q.explanation);
      showNextButton();
    });
  });
}


/* =========================================================================
   True / False
   ========================================================================= */

function buildTFBody() {
  return `
    <div class="tf-grid">
      <button class="option-btn" data-value="True">
        <span class="option-letter">T</span><span>True</span>
      </button>
      <button class="option-btn" data-value="False">
        <span class="option-letter">F</span><span>False</span>
      </button>
    </div>`;
}

function attachTFListeners(q) {
  document.querySelectorAll(".option-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      if (state.answered) return;
      state.answered = true;

      const selected  = btn.dataset.value;
      const isCorrect = selected === q.correct;

      document.querySelectorAll(".option-btn").forEach(b => {
        b.disabled = true;
        if (b.dataset.value === q.correct) b.classList.add("correct");
        if (b === btn && !isCorrect)       b.classList.add("incorrect");
      });

      recordAnswer(isCorrect, isCorrect ? 1 : 0);
      showExplanation(q.explanation);
      showNextButton();
    });
  });
}


/* =========================================================================
   Short answer — LLM grading
   =========================================================================
   Flow:
     1. Student types in textarea.
     2. Clicks "Submit Answer".
     3. If blank → mark incorrect, show model answer, skip API call.
     4. Otherwise → call POST /api/evaluate-answer.
     5. Show score badge (Correct / Partial Credit / Incorrect) + feedback.
     6. Show model answer below.
     7. Show Next button.
   ========================================================================= */

function buildSABody() {
  return `
    <textarea class="sa-textarea" id="sa-input"
      placeholder="Write your answer here, then click Submit Answer..."></textarea>
    <div class="sa-actions">
      <button class="btn btn-primary" id="submit-sa-btn">Submit Answer</button>
    </div>
    <div id="eval-result" class="hidden"></div>
    <div id="model-answer-box" class="model-answer-box hidden"></div>
  `;
}

function attachSAListeners(q) {
  document.getElementById("submit-sa-btn").addEventListener("click", () => {
    handleSASubmit(q);
  });
}

async function handleSASubmit(q) {
  if (state.answered) return;
  state.answered = true;

  const textarea = document.getElementById("sa-input");
  const btn      = document.getElementById("submit-sa-btn");
  const answer   = textarea.value.trim();

  textarea.disabled = true;
  btn.disabled      = true;

  if (!answer) {
    recordAnswer(false, 0);
    showModelAnswer(q);
    showExplanation(q.explanation);
    showNextButton();
    return;
  }

  btn.textContent = "Evaluating...";

  try {
    const result = await callEvaluateAPI({
      question:       q.question,
      model_answer:   q.model_answer,
      key_points:     q.key_points,
      student_answer: answer
    });

    const scoreMap = { correct: 1, partial: 0.5, incorrect: 0 };
    const score    = scoreMap[result.score] ?? 0;

    recordAnswer(score > 0, score);
    showEvaluationResult(result);

  } catch {
    recordAnswer(false, 0);
    showEvaluationResult({
      score:    "partial",
      feedback: "Could not reach the grading service. Compare your answer with the model answer below."
    });
  }

  showModelAnswer(q);
  showExplanation(q.explanation);
  showNextButton();
}

/** POST the student's answer to the server and return the grading result. */
async function callEvaluateAPI(payload) {
  const res = await fetch("/api/evaluate-answer", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Evaluate API error: ${res.status}`);
  return res.json();
}

/** Render the score badge + feedback below the textarea. */
function showEvaluationResult(result) {
  const labels = { correct: "Correct", partial: "Partial Credit", incorrect: "Incorrect" };
  const label  = labels[result.score] ?? result.score;

  document.getElementById("eval-result").innerHTML = `
    <div class="eval-box eval-${result.score}">
      <span class="eval-badge">${escHtml(label)}</span>
      <p class="eval-feedback">${escHtml(result.feedback)}</p>
    </div>`;
  document.getElementById("eval-result").classList.remove("hidden");
}

/** Reveal the model answer + key points. */
function showModelAnswer(q) {
  const keyPoints = (q.key_points || [])
    .map(p => `<li>${escHtml(p)}</li>`).join("");

  document.getElementById("model-answer-box").innerHTML = `
    <h4>Model Answer</h4>
    <p>${escHtml(q.model_answer || "")}</p>
    ${keyPoints ? `<h4 style="margin-top:0.75rem">Key Points</h4><ul>${keyPoints}</ul>` : ""}`;
  document.getElementById("model-answer-box").classList.remove("hidden");
}


/* =========================================================================
   Shared post-answer helpers
   ========================================================================= */

function recordAnswer(isCorrect, score) {
  state.answers[state.current] = {
    correct: isCorrect,
    score:   score !== undefined ? score : (isCorrect ? 1 : 0)
  };
  updateScoreDisplay();
}

function showExplanation(text) {
  if (!text) return;
  const card = document.getElementById("question-card");
  const box  = document.createElement("div");
  box.className = "explanation-box";
  box.innerHTML  = `<div class="expl-label">Explanation</div>${escHtml(text)}`;
  card.appendChild(box);
}

function showNextButton() {
  const isLast = state.current === state.quiz.questions.length - 1;
  const label  = isLast ? "Finish Quiz" : "Next Question";

  const row = document.createElement("div");
  row.className = "next-row";
  row.innerHTML = `<button class="btn btn-primary" id="next-btn">${label}</button>`;
  document.getElementById("question-card").appendChild(row);
  document.getElementById("next-btn").addEventListener("click", nextQuestion);
}


/* =========================================================================
   Navigation
   ========================================================================= */

function nextQuestion() {
  if (state.current < state.quiz.questions.length - 1) {
    state.current++;
    renderQuestion();
  } else {
    showResults();
  }
}


/* =========================================================================
   Results screen
   ========================================================================= */

function showResults() {
  const total      = state.quiz.questions.length;
  const totalScore = state.answers.reduce((sum, a) => sum + (a?.score ?? 0), 0);
  const pct        = Math.round((totalScore / total) * 100);

  let gradeClass = "grade-low";
  let gradeMsg   = "Keep studying! Review the explanations and try again.";
  if      (pct >= 90) { gradeClass = "grade-great"; gradeMsg = "Excellent! You have mastered this topic."; }
  else if (pct >= 70) { gradeClass = "grade-great"; gradeMsg = "Great job! Almost there."; }
  else if (pct >= 50) { gradeClass = "grade-ok";    gradeMsg = "Good effort — review the missed questions."; }

  const scoreText = Number.isInteger(totalScore) ? totalScore : totalScore.toFixed(1);
  document.getElementById("score-display").innerHTML = `
    <div class="score-circle ${gradeClass}">${pct}%</div>
    <p class="score-label">${scoreText} / ${total} points — ${gradeMsg}</p>
  `;

  const missed = state.quiz.questions.filter((_, i) => !state.answers[i]?.correct);
  if (missed.length > 0) {
    document.getElementById("missed-section").classList.remove("hidden");
    document.getElementById("missed-review").innerHTML = missed.map(q => {
      let ans = q.correct ?? "";
      if (q.type === "multiple_choice" && q.options) ans = `${q.correct}: ${q.options[q.correct] ?? ""}`;
      if (q.type === "short_answer")                 ans = q.model_answer ?? "";
      return `
        <div class="missed-item">
          <div class="missed-q">${escHtml(q.question)}</div>
          <div class="missed-a">Answer: ${escHtml(ans)}</div>
        </div>`;
    }).join("");
  }

  const concepts = state.quiz.reasoning?.key_concepts || [];
  if (concepts.length > 0) {
    document.getElementById("subtopic-section").classList.remove("hidden");
    const grid = document.getElementById("subtopic-grid");
    grid.innerHTML = concepts.map(c =>
      `<button class="subtopic-btn" data-concept="${escHtml(c)}">${escHtml(c)}</button>`
    ).join("");

    grid.querySelectorAll(".subtopic-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const concept = btn.dataset.concept;
        triggerQuizGeneration(
          `${concept} (within ${state.topic})`,
          state.difficulty,
          state.numQuestions,
          // subtopic drills always use search mode so web context broadens the scope
          false
        );
      });
    });
  }

  showScreen("results-screen");
}


/* =========================================================================
   Panel toggles
   ========================================================================= */

function initPanelToggles() {
  document.getElementById("log-toggle").addEventListener("click", () => {
    const wrap   = document.getElementById("agent-log-wrap");
    const btn    = document.getElementById("log-toggle");
    const hidden = wrap.classList.toggle("hidden");
    btn.textContent = hidden ? "Show Agent Log" : "Hide Agent Log";
  });

  document.getElementById("reasoning-summary-toggle").addEventListener("click", () => {
    const box    = document.getElementById("reasoning-box");
    const btn    = document.getElementById("reasoning-summary-toggle");
    const hidden = box.classList.toggle("hidden");
    btn.textContent = hidden ? "Show Agent Reasoning" : "Hide Agent Reasoning";
  });

  document.getElementById("sources-toggle").addEventListener("click", () => {
    document.getElementById("sources-list").classList.toggle("hidden");
  });

  document.getElementById("reasoning-toggle").addEventListener("click", () => {
    const panel  = document.getElementById("reasoning-panel");
    const btn    = document.getElementById("reasoning-toggle");
    const hidden = panel.classList.toggle("hidden");
    btn.textContent = hidden ? "Show Agent Reasoning" : "Hide Agent Reasoning";
  });

  document.getElementById("missed-toggle").addEventListener("click", () => {
    const review = document.getElementById("missed-review");
    const btn    = document.getElementById("missed-toggle");
    const hidden = review.classList.toggle("hidden");
    btn.textContent = hidden ? "Show Missed Questions" : "Hide Missed Questions";
  });
}


/* =========================================================================
   Boot
   ========================================================================= */

function init() {
  checkNotesStatus();

  document.getElementById("use-notes-checkbox").addEventListener(
    "change", handleNotesCheckboxChange
  );

  document.getElementById("quiz-form").addEventListener("submit", handleFormSubmit);

  document.getElementById("start-quiz-btn").addEventListener("click", () => {
    startQuiz(state.quiz);
  });

  document.getElementById("harder-btn").addEventListener("click", () => {
    const order   = ["Beginner", "Intermediate", "Advanced"];
    const nextIdx = Math.min(order.indexOf(state.difficulty) + 1, order.length - 1);
    triggerQuizGeneration(state.topic, order[nextIdx], state.numQuestions, state.useNotes);
  });

  document.getElementById("similar-btn").addEventListener("click", () => {
    triggerQuizGeneration(state.topic, state.difficulty, state.numQuestions, state.useNotes);
  });

  document.getElementById("new-topic-btn").addEventListener("click", () => {
    location.reload();
  });

  document.getElementById("retake-btn").addEventListener("click", () => {
    startQuiz(state.quiz);
  });

  initPanelToggles();
}

document.addEventListener("DOMContentLoaded", init);


/* =========================================================================
   Utilities
   ========================================================================= */

function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function truncate(str, max) {
  return str && str.length > max ? str.slice(0, max) + "..." : (str || "");
}
