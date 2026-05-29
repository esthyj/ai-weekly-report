// Vanilla JS state machine for the AI Weekly Report demo.
//
// Flow:
//   meta -> crawl(SSE) -> select -> summarize(SSE) -> review -> ailab(SSE) -> done
//
// Branches in the review step:
//   accept  → POST /finalize → POST /ailab
//   resummarize → POST /summarize (re-uses selected_df on the server)
//   reselect → back to article table (server keeps crawled_df cached)

const state = {
  sessionId: null,
  articles: [],
  selectedIndices: [],
  summaries: [],
  companies: [],
  // 최종 확인 단계에서 사용자가 편집을 되돌릴 수 있도록 서버 원본을 보관
  originalNewsSummary: "",
  originalAilabText: "",
};

const INSURANCE_PRESET = [
  "삼성화재", "현대해상", "DB손해보험", "KB손해보험", "메리츠화재", "토스인슈어런스",
  "삼성생명", "교보생명", "한화생명", "신한라이프", "NH농협생명", "KB라이프",
];

const STEPS = ["meta", "crawl", "select", "summarize", "review", "ailab-input", "ailab", "final-review", "done"];

// 내부 스텝 → 상단 stepper의 5개 사용자 단계 매핑
const STEP_GROUPS = [
  { group: "input", steps: ["meta"] },                              // 1. 기본 정보 입력
  { group: "collect", steps: ["crawl", "select", "summarize", "review"] }, // 2. 뉴스 수집 및 요약
  { group: "ailab", steps: ["ailab-input", "ailab"] },              // 3. 부서 내용 정리
  { group: "review", steps: ["final-review"] },                     // 4. 최종 검토
  { group: "done", steps: ["done"] },                               // 5. 생성된 자료 출력
];

// 각 화면이 무엇을 하는 단계인지 설명 (stepper 아래에 표시)
const STEP_DESCRIPTIONS = {
  "meta": "보고서 발행 호수·날짜와 검색 조건(필수 키워드·기업 키워드·기간)을 입력하세요.",
  "crawl": "입력한 조건으로 Google에서 기업별 최신 뉴스를 수집하고 있어요.",
  "select": "수집된 기사 중 보고서에 포함할 기사를 선택하세요.",
  "summarize": "선택한 기사를 AI가 핵심만 요약하고 있어요. 잠시만 기다려 주세요!",
  "review": "생성된 뉴스 요약을 검토하고, 보고서에 넣을 항목을 선택하세요.",
  "ailab-input": "금주 부서에서 진행된 주요 내용을 입력하세요.",
  "ailab": "입력한 내용을 AI가 요약하고 있어요.",
  "final-review": "뉴스 및 부서 내용 요약을 최종 확인하고 필요하면 편집하세요.",
  "done": "보고서가 완성되었어요. 필요한 파일을 다운로드하세요.",
};

// 화면별 안내 아이콘 (설명 글씨 위에 표시)
// "뉴스 수집 및 요약" 단계(crawl·select·summarize·review) 내내 newspaper.png 유지
const STEP_ICONS = {
  "meta": "/images/write.png",
  "crawl": "/images/newspaper.png",
  "select": "/images/newspaper.png",
  "summarize": "/images/newspaper.png",
  "review": "/images/newspaper.png",
};

function updateStepper(stepName) {
  const idx = STEP_GROUPS.findIndex((g) => g.steps.includes(stepName));
  if (idx < 0) return; // error 등 매핑되지 않는 화면에서는 현재 상태 유지
  document.querySelectorAll(".stepper-item").forEach((el, i) => {
    el.classList.toggle("done", i < idx);
    el.classList.toggle("active", i === idx);
  });
  const desc = document.getElementById("stepper-desc");
  if (desc) desc.textContent = STEP_DESCRIPTIONS[stepName] || "";
  // 단계별 안내 아이콘 — 매핑된 화면에서만 표시
  const icon = document.getElementById("stepper-desc-icon");
  if (icon) {
    const src = STEP_ICONS[stepName];
    if (src) {
      icon.src = src;
      icon.classList.add("show");
    } else {
      icon.classList.remove("show");
    }
  }
}

function show(stepName) {
  document.querySelectorAll(".step").forEach((el) => el.classList.remove("active"));
  const el = document.getElementById("step-" + stepName);
  if (el) el.classList.add("active");
  updateStepper(stepName);
}

function showError(message) {
  document.querySelectorAll(".step").forEach((el) => el.classList.remove("active"));
  document.getElementById("step-error").classList.add("active");
  document.getElementById("error-detail").textContent = message;
}

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${method} ${path} → ${res.status}: ${text}`);
  }
  return res.json();
}

function streamLogs(stageStream, logEl, onLine) {
  return new Promise((resolve, reject) => {
    const es = new EventSource(stageStream);
    es.addEventListener("log", (ev) => {
      try {
        const text = JSON.parse(ev.data);
        if (logEl) {
          const line = document.createElement("div");
          line.className = "line";
          // 기업 시작(🔍) / 요약 항목 시작(📝) 줄에만 구분선 표시
          const head = text.trimStart();
          if (head.startsWith("🔍") || head.startsWith("📝")) {
            line.classList.add("group-start");
          }
          line.textContent = text;
          logEl.appendChild(line);
          logEl.scrollTop = logEl.scrollHeight;
        }
        if (typeof onLine === "function") onLine(text);
      } catch (e) { /* ignore */ }
    });
    es.addEventListener("end", (ev) => {
      const payload = JSON.parse(ev.data);
      es.close();
      if (payload.status === "error") reject(new Error(payload.error || "unknown error"));
      else resolve();
    });
    es.onerror = () => {
      es.close();
      reject(new Error("SSE 연결이 끊겼습니다."));
    };
  });
}

// ============================================================
// Crawl progress view — builds company cards from pre-fetched
// categories and updates them as SSE log lines stream in.
// ============================================================

const crawlView = {
  rows: [],            // [{ category, name, status, detail, el }]
  currentCategory: null,
  currentRowIdx: null,
  total: 0,
  done: 0,

  reset() {
    this.rows = [];
    this.currentCategory = null;
    this.currentRowIdx = null;
    this.total = 0;
    this.done = 0;
  },

  build(categories) {
    const wrap = document.getElementById("crawl-companies");
    wrap.innerHTML = "";
    this.reset();

    categories.forEach((cat) => {
      const group = document.createElement("div");
      group.className = "company-group";

      const head = document.createElement("div");
      head.className = "company-group-head";
      head.innerHTML = `<span>${cat.category}</span><span class="group-count">${cat.queries.length}곳</span>`;
      group.appendChild(head);

      cat.queries.forEach((name) => {
        const row = document.createElement("div");
        row.className = "company-row pending";
        row.innerHTML = `
          <span class="status">⏳</span>
          <span class="name"></span>
          <span class="detail">대기 중</span>
        `;
        row.querySelector(".name").textContent = name;
        group.appendChild(row);

        this.rows.push({
          category: cat.category,
          name,
          status: "pending",
          detail: "대기 중",
          el: row,
        });
        this.total += 1;
      });

      wrap.appendChild(group);
    });

    this.updateProgress("뉴스를 검색하는 중...");
    document.getElementById("crawl-current").innerHTML = '<span class="spinner"></span>잠시만 기다려 주세요.';
  },

  updateProgress(label) {
    document.getElementById("crawl-progress-label").textContent = label;
    document.getElementById("crawl-progress-count").textContent = `${this.done} / ${this.total}`;
    const pct = this.total > 0 ? (this.done / this.total) * 100 : 0;
    document.getElementById("crawl-progress-fill").style.width = `${pct}%`;
  },

  renderRow(idx) {
    const r = this.rows[idx];
    if (!r) return;
    r.el.className = `company-row ${r.status}`;
    const iconMap = {
      pending: "⏳",
      searching: '<span class="spinner"></span>',
      done: "✅",
      empty: "⚠️",
    };
    r.el.querySelector(".status").innerHTML = iconMap[r.status] || "";
    r.el.querySelector(".detail").textContent = r.detail;
  },

  setCurrent(name) {
    document.getElementById("crawl-current").innerHTML =
      `<span class="spinner"></span>현재 검색 중: <strong>${name}</strong>`;
  },

  finish() {
    this.currentRowIdx = null;
    this.updateProgress("크롤링 완료");
    document.getElementById("crawl-current").textContent = "✅ 모든 기업 검색을 마쳤어요.";
  },

  // Parse one progress log line and update the view accordingly.
  handleLine(text) {
    // 카테고리 시작:  "📌 [보험사] 검색 중..."
    let m = text.match(/^📌 \[(.+)\] 검색 중/);
    if (m) {
      this.currentCategory = m[1];
      return;
    }
    // 회사 검색 시작:  "  🔍 삼성화재"
    m = text.match(/^\s*🔍\s+(.+)$/);
    if (m) {
      const name = m[1].trim();
      const idx = this.rows.findIndex(
        (r) => r.category === this.currentCategory && r.name === name && r.status === "pending"
      );
      this.currentRowIdx = idx >= 0 ? idx : null;
      if (idx >= 0) {
        this.rows[idx].status = "searching";
        this.rows[idx].detail = "검색 중...";
        this.renderRow(idx);
        this.setCurrent(name);
      }
      return;
    }
    // 선택 완료:  "    ✅ 선택: 제목..."
    m = text.match(/^\s*✅\s*선택:\s*(.+?)\.{0,3}\s*$/);
    if (m && this.currentRowIdx !== null) {
      this.rows[this.currentRowIdx].status = "done";
      this.rows[this.currentRowIdx].detail = m[1];
      this.renderRow(this.currentRowIdx);
      this.done += 1;
      this.updateProgress("뉴스를 검색하는 중...");
      this.currentRowIdx = null;
      return;
    }
    // 결과 없음:  "    ⚠️ 뉴스 없음"
    if (/⚠️.*뉴스 없음/.test(text) && this.currentRowIdx !== null) {
      this.rows[this.currentRowIdx].status = "empty";
      this.rows[this.currentRowIdx].detail = "관련 뉴스 없음";
      this.renderRow(this.currentRowIdx);
      this.done += 1;
      this.updateProgress("뉴스를 검색하는 중...");
      this.currentRowIdx = null;
    }
  },
};

// ============================================================
// Summarize progress view — one card per selected article,
// status (pending / working / done / error) driven by SSE log lines.
// ============================================================

const summarizeView = {
  rows: [],
  current: null,
  total: 0,
  done: 0,

  build(articles) {
    const wrap = document.getElementById("summarize-articles");
    wrap.innerHTML = "";
    this.rows = [];
    this.current = null;
    this.total = articles.length;
    this.done = 0;

    articles.forEach((a, i) => {
      const row = document.createElement("div");
      row.className = "summarize-row pending";
      row.innerHTML = `
        <span class="status">⏳</span>
        <span class="idx">${i + 1}</span>
        <span class="title"></span>
        <span class="detail">대기 중</span>
      `;
      row.querySelector(".title").textContent = a.title || "(제목 없음)";
      wrap.appendChild(row);
      this.rows.push({ status: "pending", detail: "대기 중", el: row, title: a.title || "" });
    });

    this.updateProgress("AI가 기사를 읽어들이는 중...");
    document.getElementById("summarize-current").innerHTML =
      '<span class="spinner"></span>잠시만 기다려 주세요.';
  },

  updateProgress(label) {
    document.getElementById("summarize-progress-label").textContent = label;
    document.getElementById("summarize-progress-count").textContent = `${this.done} / ${this.total}`;
    const pct = this.total > 0 ? (this.done / this.total) * 100 : 0;
    document.getElementById("summarize-progress-fill").style.width = `${pct}%`;
  },

  renderRow(idx) {
    const r = this.rows[idx];
    if (!r) return;
    r.el.className = `summarize-row ${r.status}`;
    const iconMap = {
      pending: "⏳",
      working: '<span class="spinner"></span>',
      done: "✅",
      error: "⚠️",
    };
    r.el.querySelector(".status").innerHTML = iconMap[r.status] || "";
    r.el.querySelector(".detail").textContent = r.detail;
  },

  setCurrent(title) {
    document.getElementById("summarize-current").innerHTML =
      `<span class="spinner"></span>요약 중: <strong></strong>`;
    document.getElementById("summarize-current").querySelector("strong").textContent = title;
  },

  markDone(idx) {
    const r = this.rows[idx];
    if (!r || r.status === "done" || r.status === "error") return;
    r.status = "done";
    r.detail = "요약 완료";
    this.renderRow(idx);
    this.done += 1;
    this.updateProgress("AI가 기사를 읽어들이는 중...");
  },

  // Parse: "  📝 요약 중... (N/M) 기사 제목..."
  //        "      ⚠️ 해당 기사 요약 실패. 건너뜁니다."
  handleLine(text) {
    let m = text.match(/^\s*📝 요약 중\.\.\.\s*\((\d+)\/(\d+)\)\s*(.+?)\.{0,3}\s*$/);
    if (m) {
      // 이전 행이 success(=실패 로그 없음)였다면 완료 처리
      if (this.current !== null) this.markDone(this.current);
      const n = parseInt(m[1], 10) - 1;
      if (this.rows[n]) {
        this.current = n;
        this.rows[n].status = "working";
        this.rows[n].detail = "AI 요약 중...";
        this.renderRow(n);
        this.setCurrent(this.rows[n].title);
      }
      return;
    }
    if (/⚠️.*요약 실패/.test(text) && this.current !== null) {
      const idx = this.current;
      this.rows[idx].status = "error";
      this.rows[idx].detail = "요약 실패 — 건너뜀";
      this.renderRow(idx);
      this.current = null;
    }
  },

  finish() {
    if (this.current !== null) this.markDone(this.current);
    this.current = null;
    this.updateProgress("요약 완료");
    document.getElementById("summarize-current").textContent = "✅ 모든 기사 요약을 마쳤어요.";
  },
};

// ============================================================
// AI Lab 요약 진행 — 단일 LLM 호출이므로 카드 형태로만 표시
// ============================================================

const ailabView = {
  reset() {
    const msg = document.getElementById("ailab-status-message");
    if (msg) msg.textContent = "잠시만 기다려 주세요...";
  },
  handleLine(text) {
    const msg = document.getElementById("ailab-status-message");
    if (msg) msg.textContent = text;
  },
  finish() {
    const msg = document.getElementById("ailab-status-message");
    if (msg) msg.textContent = "✅ 요약 완료. 잠시 후 최종 확인 화면으로 이동합니다.";
  },
};

// ============================================================
// Company tag input
// ============================================================

function renderCompanyTags() {
  const wrap = document.getElementById("cfg-companies");
  wrap.innerHTML = "";
  if (state.companies.length === 0) {
    const empty = document.createElement("span");
    empty.className = "tag-empty";
    empty.textContent = "(추가된 기업 없음)";
    wrap.appendChild(empty);
    return;
  }
  state.companies.forEach((name, idx) => {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.innerHTML = `<span class="tag-text"></span><button type="button" class="tag-x" aria-label="삭제">✕</button>`;
    tag.querySelector(".tag-text").textContent = name;
    tag.querySelector(".tag-x").addEventListener("click", () => {
      state.companies.splice(idx, 1);
      renderCompanyTags();
    });
    wrap.appendChild(tag);
  });
}

function addCompanyFromInput() {
  const input = document.getElementById("cfg-company-input");
  const raw = input.value.trim();
  if (!raw) return;
  if (state.companies.includes(raw)) {
    input.value = "";
    return;
  }
  state.companies.push(raw);
  input.value = "";
  renderCompanyTags();
}

// ============================================================
// Step handlers
// ============================================================

async function startCrawl() {
  const number = document.getElementById("meta-number").value.trim();
  const date = document.getElementById("meta-date").value.trim();
  if (!number || !date) {
    alert("발행 호수와 날짜를 입력하세요.");
    return;
  }
  // 입력창에 남아있는 미확정 기업명도 자동 추가
  addCompanyFromInput();
  if (state.companies.length === 0) {
    alert("최소 1개 이상의 기업을 추가하세요.");
    return;
  }

  const keyword = document.getElementById("cfg-keyword").value.trim();
  const daysRaw = document.getElementById("cfg-days").value.trim();
  const days = parseInt(daysRaw, 10);
  if (!Number.isFinite(days) || days < 1) {
    alert("검색 기간은 1 이상의 숫자여야 합니다.");
    return;
  }

  state.metaNumber = number;
  state.metaDate = date;

  try {
    const { session_id, companies } = await api("POST", "/api/session", {
      companies: state.companies,
      required_keyword: keyword,
      days,
    });
    state.sessionId = session_id;
    show("crawl");
    document.getElementById("crawl-log").innerHTML = "";
    // 단일 "사용자 지정" 카테고리로 진행 카드 구성
    crawlView.build([{ category: "사용자 지정", queries: companies }]);

    await streamLogs(
      `/api/${session_id}/crawl/stream`,
      document.getElementById("crawl-log"),
      (line) => crawlView.handleLine(line),
    );
    crawlView.finish();

    const { articles } = await api("GET", `/api/${session_id}/articles`);
    state.articles = articles;
    renderArticles();
    show("select");
  } catch (e) {
    showError(e.message);
  }
}

function renderArticles() {
  const tbody = document.querySelector("#articles-table tbody");
  tbody.innerHTML = "";
  state.articles.forEach((a, idx) => {
    const tr = document.createElement("tr");
    const oneBased = idx + 1;
    const keyword = a.search_keyword || a.company || "";
    tr.innerHTML = `
      <td><input type="checkbox" data-idx="${oneBased}" /></td>
      <td>${oneBased}</td>
      <td>${keyword}</td>
      <td>${a.score}</td>
      <td><a href="${a.link}" target="_blank" rel="noopener">${a.title}</a></td>
    `;
    tbody.appendChild(tr);
  });
}

async function startSummarize() {
  const checked = Array.from(
    document.querySelectorAll("#articles-table input[type=checkbox]:checked")
  ).map((el) => parseInt(el.dataset.idx, 10));
  if (checked.length < 1) {
    alert("기사를 1개 이상 선택하세요.");
    return;
  }
  state.selectedIndices = checked;

  try {
    await api("POST", `/api/${state.sessionId}/select`, {
      indices: checked,
      number: state.metaNumber,
      date: state.metaDate,
    });
    await api("POST", `/api/${state.sessionId}/summarize`);
    show("summarize");
    { const _sl = document.getElementById("summarize-log"); if (_sl) _sl.innerHTML = ""; }
    const selectedArticles = checked.map((idx) => state.articles[idx - 1]);
    summarizeView.build(selectedArticles);
    await streamLogs(
      `/api/${state.sessionId}/summarize/stream`,
      document.getElementById("summarize-log"),
      (line) => summarizeView.handleLine(line),
    );
    summarizeView.finish();
    const { summaries } = await api("GET", `/api/${state.sessionId}/summaries`);
    state.summaries = summaries;
    renderSummaries();
    show("review");
  } catch (e) {
    showError(e.message);
  }
}

// 요약 텍스트([Title]/[SummaryN]/[Insight])를 태그 없이 스타일 HTML로 변환.
//  - Title  → 볼드
//  - Summary → 줄별 • 불릿
//  - Insight → ➔ 화살표
const SUMMARY_SECTION_RE = /\[(Title|Summary\d*|Insight)\]\s*/gi;
function summaryToStyledHtml(text) {
  if (!text) return "";
  const matches = [...text.matchAll(SUMMARY_SECTION_RE)];
  if (matches.length === 0) {
    return `<div class="sum-summary">${escapeHtml(text.trim())}</div>`;
  }
  const parts = [];
  matches.forEach((m, i) => {
    const tag = m[1].toLowerCase();
    const start = m.index + m[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
    const content = text.slice(start, end).trim();
    if (!content) return;
    if (tag === "title") {
      parts.push(`<div class="sum-title">${escapeHtml(content)}</div>`);
    } else if (tag.startsWith("summary")) {
      content.split("\n").map((l) => l.trim()).filter(Boolean).forEach((line) => {
        parts.push(`<div class="sum-summary">${escapeHtml(line)}</div>`);
      });
    } else if (tag === "insight") {
      parts.push(`<div class="sum-insight">${escapeHtml(content)}</div>`);
    }
  });
  return parts.join("");
}

function renderSummaries() {
  const wrap = document.getElementById("summaries-list");
  wrap.innerHTML = "";
  state.summaries.forEach((s) => {
    const card = document.createElement("div");
    card.className = "summary-card checked";

    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" data-idx="${s.index}" checked />`;

    const body = document.createElement("div");
    body.className = "summary-body";
    body.innerHTML = summaryToStyledHtml(s.summary);

    card.appendChild(label);
    card.appendChild(body);

    const cb = card.querySelector("input");
    cb.addEventListener("change", () => {
      card.classList.toggle("checked", cb.checked);
    });
    wrap.appendChild(card);
  });
}

async function accept() {
  const include = Array.from(
    document.querySelectorAll("#summaries-list input[type=checkbox]:checked")
  ).map((el) => parseInt(el.dataset.idx, 10));
  if (include.length < 1) {
    alert("포함할 요약을 1개 이상 선택하세요.");
    return;
  }

  try {
    await api("POST", `/api/${state.sessionId}/finalize`, {
      include_indices: include,
    });
    show("ailab-input");
    document.getElementById("ailab-content").focus();
  } catch (e) {
    showError(e.message);
  }
}

async function summarizeAilab() {
  const content = document.getElementById("ailab-content").value.trim();
  if (content.length < 10) {
    alert("AI Lab 콘텐츠를 10자 이상 입력하세요.");
    return;
  }

  try {
    await api("POST", `/api/${state.sessionId}/ailab`, { ailab_content: content });
    show("ailab");
    { const _al = document.getElementById("ailab-log"); if (_al) _al.innerHTML = ""; }
    ailabView.reset();
    await streamLogs(
      `/api/${state.sessionId}/ailab/stream`,
      document.getElementById("ailab-log"),
      (line) => ailabView.handleLine(line),
    );
    ailabView.finish();
    const { combined_summary, ailab_text } = await api(
      "GET", `/api/${state.sessionId}/final-content`
    );
    state.originalNewsSummary = combined_summary;
    state.originalAilabText = ailab_text;
    show("final-review");
    setFinalReviewContent(combined_summary, ailab_text);
  } catch (e) {
    showError(e.message);
  }
}

async function confirmAndGeneratePpt() {
  const newsEl = document.getElementById("final-news-summary");
  const ailabEl = document.getElementById("final-ailab-summary");
  const combined = serializeEditor(newsEl).trim();
  const ailab = serializeEditor(ailabEl).trim();
  if (!combined || !ailab) {
    alert("뉴스 요약과 AI Lab 요약 모두 비어있지 않아야 합니다.");
    return;
  }

  const btn = document.getElementById("btn-confirm-ppt");
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = "PPT 생성 중...";
  try {
    await api("POST", `/api/${state.sessionId}/ppt`, {
      combined_summary: combined,
      ailab_text: ailab,
    });
    document.getElementById("btn-download").href = `/api/${state.sessionId}/download`;
    show("done");
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

function backToAilabInput() {
  show("ailab-input");
  document.getElementById("ailab-content").focus();
}

function setFinalReviewContent(combinedSummary, ailabText) {
  const newsEl = document.getElementById("final-news-summary");
  const ailabEl = document.getElementById("final-ailab-summary");
  newsEl.innerHTML = plainTextToHtml(normalizeContent(combinedSummary));
  ailabEl.innerHTML = plainTextToHtml(normalizeContent(ailabText));
  applySectionStyles(newsEl);
  applySectionStyles(ailabEl);
}

function resetEdits() {
  if (!confirm("편집한 내용을 모두 버리고 AI가 생성한 원본으로 되돌릴까요?")) return;
  setFinalReviewContent(state.originalNewsSummary, state.originalAilabText);
}

// ============================================================
// Rich text editor helpers
// ============================================================

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// 평문 → contenteditable 초기 innerHTML. 줄별 <div>로 분리해 두면
// (1) 섹션 헤더/본문 라인에 data-sec 속성을 붙여 시각 스타일 적용,
// (2) 사용자가 Enter로 추가하는 새 줄도 동일한 div 구조로 합류하기 쉬움.
function plainTextToHtml(text) {
  const lines = (text || "").split("\n");
  return lines
    .map((line) => `<div>${escapeHtml(line) || "<br>"}</div>`)
    .join("");
}

// 편집창의 각 줄(직접 자식 element)에 섹션 컨텍스트를 부여.
// 헤더([Title]/[SummaryN]/[Insight] 단독 라인)는 data-sec="header",
// 그 아래 줄들은 마지막 헤더 종류에 따라 title-body / summary-body / insight-body.
// 빈 줄은 data-sec를 제거 — 기사 사이 간격용 plain blank로 렌더.
const SECTION_HEADER_RE = /^\s*\[(Title|Summary\d*|Insight)\]\s*$/i;
function applySectionStyles(editor) {
  let active = null; // 'title' | 'summary' | 'insight' | null
  for (const child of editor.children) {
    const text = (child.textContent || "").trim();
    if (text === "") {
      if (child.hasAttribute("data-sec")) child.removeAttribute("data-sec");
      continue;
    }
    const m = SECTION_HEADER_RE.exec(text);
    if (m) {
      const tag = m[1].toLowerCase();
      active = tag.startsWith("summary") ? "summary" : tag;
      if (child.getAttribute("data-sec") !== "header") {
        child.setAttribute("data-sec", "header");
      }
    } else if (active) {
      const v = `${active}-body`;
      if (child.getAttribute("data-sec") !== v) child.setAttribute("data-sec", v);
    } else if (child.hasAttribute("data-sec")) {
      child.removeAttribute("data-sec");
    }
  }
}

// 서버에서 받은 본문을 편집창에 띄우기 전에 한 번 정돈.
//  - 비어있는 섹션(빈 [Summary3] 등)은 통째로 제거
//  - 한 기사 안에서는 섹션 사이 빈 줄·Enter 모두 제거 (Title→Summary→Insight 직결)
//  - 기사 경계 ([Insight] → 다음 [Title])에만 빈 줄 1개 유지
const SECTION_TAG_GLOBAL_RE = /\[(Title|Summary\d*|Insight)\]\s*/gi;
function normalizeContent(text) {
  if (!text) return "";
  const matches = [...text.matchAll(SECTION_TAG_GLOBAL_RE)];
  if (matches.length === 0) return text;

  const sections = matches.map((m, i) => {
    const tag = m[1];
    const start = m.index + m[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
    // 섹션 본문 내부: 각 줄 trim + 빈 줄 제거
    const cleaned = text.slice(start, end)
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0)
      .join("\n");
    return [tag, cleaned];
  }).filter(([_, c]) => c.length > 0);

  if (sections.length === 0) return text;

  // [Title]을 경계로 기사 단위 묶음
  const articles = [];
  for (const [tag, content] of sections) {
    if (tag.toLowerCase() === "title" || articles.length === 0) {
      articles.push([]);
    }
    articles[articles.length - 1].push([tag, content]);
  }

  // 기사 내부는 \n으로 직결, 기사 사이는 \n\n (= Enter 1개 = 빈 줄 1개)
  return articles
    .map((secs) => secs.map(([t, c]) => `[${t}]\n${c}`).join("\n"))
    .filter((s) => s.length > 0)
    .join("\n\n");
}

// 툴바 버튼: 선택 영역에 인라인 스타일을 적용.
// data-size="10|12|14|16" → font-size 적용
// data-color="#c00000" → 색상 적용 / data-color="reset" → 색상 제거
// data-cmd="bold|italic|underline|removeFormat" → execCommand
function handleToolbarClick(ev) {
  const btn = ev.target.closest("button");
  if (!btn) return;
  const toolbar = btn.closest(".rich-toolbar");
  if (!toolbar) return;
  const targetId = toolbar.dataset.target;
  const editor = document.getElementById(targetId);
  if (!editor) return;

  // 버튼 클릭으로 selection이 사라지지 않도록 처리는 mousedown에서 이미 수행됨
  editor.focus();

  const cmd = btn.dataset.cmd;
  const size = btn.dataset.size;
  const color = btn.dataset.color;

  if (cmd) {
    document.execCommand(cmd, false, null);
    return;
  }
  if (size) {
    wrapSelectionStyle(editor, { fontSize: `${size}pt` });
    return;
  }
  if (color) {
    document.execCommand("styleWithCSS", false, true);
    document.execCommand("foreColor", false, color);
    return;
  }
}

// 현재 선택을 <span style="...">로 감쌈. 선택이 없으면 무시.
function wrapSelectionStyle(editor, styles) {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;
  const range = sel.getRangeAt(0);
  if (range.collapsed) return;
  if (!editor.contains(range.commonAncestorContainer)) return;

  const span = document.createElement("span");
  Object.entries(styles).forEach(([k, v]) => {
    span.style[k] = v;
  });
  try {
    range.surroundContents(span);
  } catch {
    // surroundContents가 partial node selection에 실패할 수 있음 — 폴백
    const frag = range.extractContents();
    span.appendChild(frag);
    range.insertNode(span);
  }
  // 선택을 새 span 안쪽으로 유지
  sel.removeAllRanges();
  const newRange = document.createRange();
  newRange.selectNodeContents(span);
  sel.addRange(newRange);
}

// contenteditable DOM → 인라인 마크업 직렬화
//   {b}/{i}/{u}/{size=N}/{color=#rrggbb} ... {/...}
// 줄바꿈은 <br> 또는 <div>/<p> 경계에서 \n으로. 줄바꿈 직전에는 열린 태그를 모두 닫고
// 다음 줄에서 다시 열어 — 줄 단위로 파싱되는 백엔드(parse_sections + splitlines)에서
// 서식이 떨어지지 않도록 함.
function serializeEditor(root) {
  const out = [];
  const stack = [];

  function tagClose(t) {
    const base = t.startsWith("size=") ? "size"
               : t.startsWith("color=") ? "color"
               : t;
    return `{/${base}}`;
  }
  function pushTag(t) { stack.push(t); out.push(`{${t}}`); }
  function popTag() { out.push(tagClose(stack.pop())); }

  function emitNewline() {
    const snapshot = [...stack];
    for (let i = stack.length - 1; i >= 0; i--) out.push(tagClose(stack[i]));
    stack.length = 0;
    out.push("\n");
    snapshot.forEach(pushTag);
  }

  function lastEndsWithNewline() {
    for (let i = out.length - 1; i >= 0; i--) {
      const chunk = out[i];
      if (chunk === "" ) continue;
      return chunk.endsWith("\n");
    }
    return true; // 아직 아무것도 출력 안 한 상태 == 줄 시작
  }

  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      out.push(node.nodeValue);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;

    const tag = node.tagName.toLowerCase();
    if (tag === "br") { emitNewline(); return; }

    const isBlock = tag === "div" || tag === "p";
    if (isBlock && !lastEndsWithNewline()) emitNewline();

    // 이 요소가 추가하는 인라인 서식
    const openTags = [];
    const cs = node.style;
    const fontSize = parseSize(cs.fontSize);
    const color = parseColor(cs.color);

    if (tag === "b" || tag === "strong" || cs.fontWeight === "bold" || cs.fontWeight === "700") {
      openTags.push("b");
    }
    if (tag === "i" || tag === "em" || cs.fontStyle === "italic") {
      openTags.push("i");
    }
    if (tag === "u" || (cs.textDecoration && cs.textDecoration.indexOf("underline") !== -1)) {
      openTags.push("u");
    }
    if (fontSize) openTags.push(`size=${fontSize}`);
    if (color) openTags.push(`color=${color}`);

    openTags.forEach(pushTag);
    for (const child of node.childNodes) walk(child);
    for (let i = 0; i < openTags.length; i++) popTag();
  }

  for (const child of root.childNodes) walk(child);
  return out.join("");
}

// "16pt" → 16 (int); 그 외 단위/유효하지 않으면 null
function parseSize(fontSize) {
  if (!fontSize) return null;
  const m = /^(\d+(?:\.\d+)?)pt$/i.exec(fontSize.trim());
  if (!m) return null;
  return Math.round(parseFloat(m[1]));
}

// "rgb(192, 0, 0)" / "#c00000" → "#c00000" 정규화; 못 읽으면 null
function parseColor(color) {
  if (!color) return null;
  const c = color.trim().toLowerCase();
  if (c === "inherit" || c === "" || c === "currentcolor") return null;
  let m = /^#([0-9a-f]{6})$/i.exec(c);
  if (m) return `#${m[1].toLowerCase()}`;
  m = /^#([0-9a-f]{3})$/i.exec(c);
  if (m) {
    const [r, g, b] = m[1];
    return `#${r}${r}${g}${g}${b}${b}`;
  }
  m = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(c);
  if (m) {
    const toHex = (n) => parseInt(n, 10).toString(16).padStart(2, "0");
    return `#${toHex(m[1])}${toHex(m[2])}${toHex(m[3])}`;
  }
  return null;
}

async function resummarize() {
  // 서버에 캐시된 selected_df 재사용 — 같은 기사로 다시 요약 시작
  try {
    await api("POST", `/api/${state.sessionId}/summarize`);
    show("summarize");
    { const _sl = document.getElementById("summarize-log"); if (_sl) _sl.innerHTML = ""; }
    const selectedArticles = state.selectedIndices.map((idx) => state.articles[idx - 1]);
    summarizeView.build(selectedArticles);
    await streamLogs(
      `/api/${state.sessionId}/summarize/stream`,
      document.getElementById("summarize-log"),
      (line) => summarizeView.handleLine(line),
    );
    summarizeView.finish();
    const { summaries } = await api("GET", `/api/${state.sessionId}/summaries`);
    state.summaries = summaries;
    renderSummaries();
    show("review");
  } catch (e) {
    showError(e.message);
  }
}

function reselect() {
  // 크롤링 캐시(서버 측 crawled_df)는 그대로, UI만 select 화면으로 복귀.
  show("select");
}

function restart() {
  state.sessionId = null;
  state.articles = [];
  state.summaries = [];
  state.companies = [];
  state.originalNewsSummary = "";
  state.originalAilabText = "";
  document.getElementById("final-news-summary").innerHTML = "";
  document.getElementById("final-ailab-summary").innerHTML = "";
  document.getElementById("meta-number").value = "";
  document.getElementById("meta-date").value = "";
  document.getElementById("cfg-keyword").value = "";
  document.getElementById("cfg-days").value = "";
  document.getElementById("cfg-company-input").value = "";
  document.getElementById("ailab-content").value = "";
  renderCompanyTags();
  show("meta");
}

// ============================================================
// Wire up
// ============================================================
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-start").addEventListener("click", startCrawl);
  document.getElementById("btn-summarize").addEventListener("click", startSummarize);
  document.getElementById("btn-accept").addEventListener("click", accept);
  document.getElementById("btn-resummarize").addEventListener("click", resummarize);
  document.getElementById("btn-reselect").addEventListener("click", reselect);
  document.getElementById("btn-generate-ppt").addEventListener("click", summarizeAilab);
  document.getElementById("btn-confirm-ppt").addEventListener("click", confirmAndGeneratePpt);
  document.getElementById("btn-back-ailab").addEventListener("click", backToAilabInput);
  document.getElementById("btn-reset-edits").addEventListener("click", resetEdits);

  // 최종 확인 — 툴바 클릭 위임 + selection 보존 + 붙여넣기 정화
  document.querySelectorAll(".rich-toolbar").forEach((bar) => {
    // mousedown 단계에서 기본동작 차단 — 안 하면 클릭 순간 contenteditable의 selection이 풀림
    bar.addEventListener("mousedown", (e) => {
      if (e.target.closest("button")) e.preventDefault();
    });
    bar.addEventListener("click", handleToolbarClick);
  });
  // Enter로 새 줄이 들어올 때 항상 <div>로 감싸지도록 (Firefox 등 호환)
  try { document.execCommand("defaultParagraphSeparator", false, "div"); } catch {}

  ["final-news-summary", "final-ailab-summary"].forEach((id) => {
    const el = document.getElementById(id);
    // 외부 HTML 오염 방지 — 항상 plain text로 붙여넣기
    el.addEventListener("paste", (e) => {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, text);
    });
    // 사용자가 줄을 추가/삭제하면 섹션 컨텍스트가 바뀌므로 매 입력마다 재스캔
    el.addEventListener("input", () => applySectionStyles(el));
  });
  document.getElementById("btn-restart").addEventListener("click", restart);
  document.getElementById("btn-error-restart").addEventListener("click", restart);

  // 태그 입력
  const tagInput = document.getElementById("cfg-company-input");
  tagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCompanyFromInput();
    }
  });
  document.getElementById("btn-clear-companies").addEventListener("click", () => {
    state.companies = [];
    renderCompanyTags();
  });
  document.getElementById("btn-preset-insurance").addEventListener("click", () => {
    INSURANCE_PRESET.forEach((name) => {
      if (!state.companies.includes(name)) state.companies.push(name);
    });
    renderCompanyTags();
  });

  renderCompanyTags();
  show("meta");
});
