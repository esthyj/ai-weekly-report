# 오렌지픽 (OrangePick)
### AI 기반 주간 리포트 자동 생성 프로그램

> 신선한 뉴스를 빠르게 수집·정제하고(**오렌지**), 사람이 개입해 최종 결과물을 선택한다(**픽**)

바이브코딩 경진대회 제출작 · 발표자: 전예은 사원

---

## 목차

1. 왜 만들었나 — 문제 발견
2. 어떻게 동작하나 — AI 자동화 + 사람 검수
3. 기대 효과 — 정량 · 정성 · 확장성
4. 기술 아키텍처
5. 핵심 기술 포인트
6. 시연 & 마무리

---

# 1. 왜 만들었나

## 신입사원의 첫 업무, 그리고 발견한 비효율

- 입사 후 첫 업무로 **주간 AI 리포트 작성**을 맡음
- 타 보험사가 추진하는 AI 과제를 조사·요약하고 **인사이트**를 정리해 리포트로 담는 일
- 직접 작성하며 깨달은 점 → **매주 똑같은 과정이 반복**된다

### 매주 반복되던 4단계

| 단계 | 작업 | 성격 |
|---|---|---|
| ① | 여러 뉴스를 일일이 검색 | 반복·기계적 |
| ② | 기사 핵심 요약 | 반복·기계적 |
| ③ | 인사이트 정리 | 반복·기계적 |
| ④ | 정해진 PPT 양식에 옮겨 담기 | 반복·기계적 |

> **"이 반복을 자동화하면 업무 효율과 리포트 품질을 동시에 올릴 수 있겠다"** — 제작의 계기

---

## 그냥 ChatGPT/Claude로 만들면 안 될까?

최근에는 생성형 AI로 리포트를 빠르게 만들 수 있음. 하지만…

- ❌ AI가 **처음부터 끝까지** 작성한 결과물은 보는 사람이 *'AI가 만들었다'*는 걸 쉽게 알아챔
- ❌ AI 특유의 **장황한 설명** 탓에 핵심이 한눈에 들어오지 않음

### 그래서 목표를 바꿨다

> 단순히 **빠르게 생성**하는 결과물이 아니라 → **퀄리티 높은** 결과물

**해결 전략: 작업을 두 가지로 나눈다**

- 🤖 **반복적·기계적 작업** (뉴스 수집·요약·인사이트 도출·PPT 제작) → **AI로 자동화**
- 🧑 **판단이 필요한 순간** (기사 선택·요약 선택·최종 검수) → **사람이 직접 선택**

= **AI의 속도** + **사람 검수의 완성도**

---

# 2. 어떻게 동작하나

## Human-in-the-Loop 파이프라인

```
[사람] 메타정보·키워드 입력
        ↓
[AI]  뉴스 크롤링  →  기사 요약  →  인사이트 도출
        ↓
[사람] 관련도 높은 기사 선별 / 리포트에 반영할 요약 선택
        ↓
[AI]  AI Lab 부서 내용 정리  +  기사별 이미지 생성
        ↓
[사람] AI가 작성한 내용 최종 검토
        ↓
[AI]  지정된 글씨체·위치에 맞춰 PPT 자동 생성
```

**핵심 설계**: 자동화로 처리할 부분과 사람이 개입해 판단할 부분을 명확히 구분

---

## 기존 업무 → 오렌지픽 자동화 매핑

| 기존 수작업 | 오렌지픽 |
|---|---|
| ① 여러 뉴스를 일일이 검색 | **자동 뉴스 크롤링**으로 관련 기사 일괄 수집 |
| ② 기사 핵심 요약 | **AI가 기사 핵심 자동 요약** |
| ③ 인사이트 정리 | **AI가 인사이트 도출** |
| ④ PPT 양식에 옮겨 담기 | **지정한 글씨체·위치에 맞춰 PPT 자동 생성** |

---

## 사람이 개입하는 3개의 체크포인트

오렌지픽은 무조건 자동이 아니라, **중요한 순간마다 사람이 핸들을 잡는다**

1. **기사 선택** — AI가 수집한 후보 중 관련도 높은 기사만 선별
2. **요약 선택** — 생성된 요약 중 리포트에 실을 것만 채택 (재요약·기사 재선택 루프 지원)
3. **최종 검수** — AI가 쓴 문장과 생성 이미지를 사람이 확인 후 확정


---

# 3. 기대 효과

## 정량 효과 — 3일 → 10분

| 구분 | 직접 작성 | 오렌지픽 도입 후 |
|---|---|---|
| 한 호수당 소요 시간 | **꼬박 3일** | **약 10분** |

### 10분의 내역

| 단계 | 담당 | 시간 |
|---|---|---|
| 호수·날짜·검색 키워드 입력 | 🧑 사람 | 1분 |
| 뉴스 검색·요약·인사이트 → 관련 기사/요약 선택 | 🤖→🧑 | 3분 |
| AI Lab 부서 내용 정리 | 🤖 AI | — |
| AI가 작성한 내용 최종 검토 | 🧑 사람 | 6분 |
| 지정 양식으로 PPT 자동 생성 | 🤖 AI | — |

> 반복 작업은 자동화, **선택·검토가 필요한 순간에만** 직접 개입 → 전체 시간 대폭 단축

---

## 정성 효과 & 향후 활용

### 정성 효과 — 도메인 지식의 공백을 메우다

- 신입으로서 **언더라이팅, 완전판매 모니터링** 등 보험업 이해가 부족했음
- 기사 기반으로 **한화손보에 적용할 인사이트**를 도출하기 어려웠음
- AI의 도움으로 관련 내용 기반 인사이트를 **한층 높은 완성도**로 작성

### 향후 활용 방안 — 부서를 막론한 확장

- 사내 타 부서에도 **정해진 양식의 주기적 리포트** 업무가 적지 않음
- 반복 작업을 바이브코딩으로 자동화하면 → **부서 불문 리포트 작성 시간 대폭 단축**

---

# 4. 기술 아키텍처

## 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│  진입점:  main.py (CLI)   /   app.py (FastAPI 웹 데모)      │
└─────────────────────────────────────────────────────────┘
        │
        ▼  순차 파이프라인
  ┌──────────────┬──────────────┬──────────────┬──────────────┐
  │ news_crawler │ news_summarize│ ailab_summarize│ ppt_maker   │
  │  뉴스 크롤링   │  기사 요약     │ AI Lab 요약    │ PPT 생성     │
  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
         │              │              │              │
         │      ┌───────┴──────────────┴───────┐      │
         │      │      llm_client (Claude)      │      │
         │      └──────────────────────────────┘      │
   image_generator
   (Nano Banana Pro)
```


## 사용 기술 스택

| 영역 | 기술 |
|---|---|
| 언어 | Python 3 |
| LLM | **Anthropic Claude (`claude-opus-4-8`)** — 요약·인사이트·이미지 프롬프트 |
| 이미지 생성 | **Gemini `gemini-3-pro-image` (Nano Banana Pro)** — 글자 없는 비주얼 |
| 뉴스 수집 | `feedparser` (Google News RSS) · `googlenewsdecoder` · `newspaper3k` |
| 문서 생성 | `python-pptx` (PPT) |
| 웹 데모 | FastAPI · SSE 스트리밍 · 정적 프런트엔드 |
| 데이터 | `pandas` (중간 데이터/Excel 감사 추적) |

---

# 5. 핵심 기술 포인트

## ① 스마트 뉴스 크롤링 & 스코어링

- **카테고리별 기업 목록**(`SEARCH_CATEGORIES`)을 Google News RSS로 일괄 검색
  - 예: 삼성화재, 현대해상, 한화생명, 신한라이프 등 + 필수 키워드 `AI`
- **우선순위 키워드 가중치 스코어링**으로 관련도 높은 기사 자동 선별

```python
PRIORITY_KEYWORDS = {"챗봇":10, "생성형":10, "LLM":10, "에이전트":10,
                     "RAG":10, "출시":8, "도입":8, "개발":8, ...}
# 제목에 등장하면 가중치 2배
score += weight * 2 if keyword in title else weight
```

- `EXCLUDE_KEYWORDS`(주가·급등·종목 등)로 노이즈 기사 제거
- 기업당 기사 5건 검색 → 최고 점수 기사 1건 제시

---

## ② 템플릿 충실 PPT 자동 생성

회사 공식 템플릿(`AIWeeklyReport_format.pptx`)의 **도형 위치·서식을 그대로 채움**

```python
TAG_STYLES = {
  "title":   ("",   "한화고딕 B",  12, ...),
  "summary": ("• ", "한화고딕 EL", 12, ...),
  "insight": ("➔ ", "한화고딕 B",  12, underline=True, ...),
}
```

- 정규식 `TAG_RE`로 `[Tag]` 섹션 추출 → 태그별 폰트·크기·밑줄·불릿 자동 적용
- **한화고딕 B/EL/L** 지정 폰트로 회사 디자인 가이드 준수
- 기사별 **AI 생성 이미지**를 우측에 배치 (글자 없는 순수 비주얼)

---

## ③ 기사별 AI 이미지 생성 (선택)

- 기사 본문 → Claude가 **영문 이미지 프롬프트** 생성 → Gemini로 이미지 생성
- "이미지에 **어떤 글자도 넣지 않는다**" 제약 → 디자인을 해치지 않는 깔끔한 비주얼
- 사람이 **포함 / 제외 / 재생성** 선택 → 마음에 들 때까지 반복

## ④ 웹 데모

- FastAPI 기반 웹 UI로 CLI 없이도 클릭만으로 전 과정 진행
- **SSE 스트리밍**으로 크롤링·요약 진행 상황 실시간 표시

---

# 5-2. 실제 사용한 프롬프트

## 뉴스 기사 요약 — System (`news_summarize.py`)

```
You are a professional AI analyst specializing in Insurance and AI services. You write concise, structured, and business-oriented summaries in Korean.
```

---

## 뉴스 기사 요약 — User Prompt (`news_summarize.py`)

```
<task>
Analyze the following news article and produce a structured Korean output.

<requirements>
1. Generate EXACTLY [Summary1] and [Summary2] — always two, never one or three.
  - Do NOT attempt to summarize the entire article.
  - Focus on high-impact facts, decisions, or implications.
  - Do NOT output [Summary3] or any summary beyond [Summary2].
2. Write ONE insight sentence for an insurance company use case.
3. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
4. Use professional Korean business tone.
5. For [Title], use the original title provided below EXACTLY as-is. Do NOT modify, translate, or rephrase it.
6. For [Summary], [Insight], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
7. In insight, when referring to "our company" in Korean, use "당사".
8. Please write each [Summary] and [Insight] between 80 and 120 characters.
9. Avoid redundancy: [Title], [Summary], and [Insight] must each contain unique information without overlapping content or repeating the same expressions.

<original_title>
{title}

<output_format>
[Title]
(Copy the original title exactly as provided above. Do not change anything.)

[Summary1]
First key point (e.g., new service/product and its features)

[Summary2]
Second key point (e.g., AI technologies applied)

[Insight]
Suggest a concrete way this service or technology could be applied in our insurance company, along with expected benefits if applicable.
(e.g., underwriting, claims, customer service, sales, marketing, risk management).

<article>
{content}
```

---

## AI Lab 요약 — System & User (`ailab_summarize.py`)

**System**
```
You are a professional AI analyst specializing in Insurance and AI services. You write concise, structured, and business-oriented summaries in Korean.
```

**User**
```
<task>
Analyze the following news article and produce a structured Korean output.

<requirements>
1. Please generate exactly one sentence each after [Summary1] and [Summary2].
2. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
3. Use professional Korean business tone.
4. For [Title], Use noun-only endings
5. For [Summary1], [Summary2], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
6. Please write [Summary1] and [Summary2] each within 150 characters.

<output_format>
[Title]
Generate a title that summarizes the content of the news.

[Summary1]
Write one keypoint about the news article.

[Summary2]
Write another keypoint about the news article.

<article>
{content}
```


---

## 이미지 프롬프트 생성 — System (`image_generator.py`)

Claude가 한글 기사 → 영문 이미지 프롬프트로 변환하는 아트 디렉터 역할

```
You are an art director selecting editorial photography concepts for a Korean insurance company's weekly AI/finance newsletter. Given a Korean news article, write ONE concise English image-generation prompt (2-4 sentences) describing a realistic, professional, photographic image that visually represents the article's theme. Describe a believable real-world scene, the setting, mood, composition and a corporate color palette (blues, teals, warm accents). Use a realistic, photorealistic style with natural lighting — avoid abstract, conceptual or surreal elements. Do not include real brand logos or identifiable real people. If the scene includes any people, describe them as Korean (East Asian people of Korean ethnicity, with Korean facial features), styled as anonymous, non-identifiable individuals. Never include any words, letters or text in the described scene. Output ONLY the prompt text, nothing else.
```

---

## 이미지 생성 강제 규칙 (`image_generator.py`)

생성된 프롬프트 끝에 항상 덧붙여 Gemini(`gemini-3-pro-image`)로 생성

**STYLE_RULE — 사실적·포토리얼리스틱 강제**
```
Render in a realistic, photorealistic style — natural lighting, real-world settings and materials, true-to-life detail, like a professional photograph. Avoid abstract, conceptual, cartoonish, low-poly, neon-glow, holographic or surreal/sci-fi looks. Any people shown must appear Korean (East Asian, of Korean ethnicity, with Korean facial features).
```

**NO_TEXT_RULE — 글자 절대 금지**
```
ABSOLUTELY CRITICAL: Do NOT render any text, letters, numbers, words, captions, labels, titles, logos, watermarks, signage, UI text, or typography anywhere in the image. The image must contain zero readable characters. Pure wordless image only.
```

---

# 6. 마무리

## 오렌지픽이 증명한 것

- ✅ **반복은 AI에게, 판단은 사람에게** — 역할을 나누면 속도와 품질을 모두 잡을 수 있다
- ✅ **3일 → 10분**, 그리고 더 높은 인사이트 완성도
- ✅ 회사 템플릿·폰트까지 충실히 지키는 **바로 쓸 수 있는 결과물**
- ✅ 어느 부서든 적용 가능한 **확장성** — 주기적 리포트 업무의 새 표준

> 신선한 뉴스를 빠르게 수집·정제하고(오렌지), 사람이 마지막을 선택한다(픽).
> **OrangePick** 🍊

### 감사합니다 — 시연 (demo.mp4)를 참고하세요.
