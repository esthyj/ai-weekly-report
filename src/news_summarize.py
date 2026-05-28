import pandas as pd
from typing import Callable, Optional
from .llm_client import call_llm
from .config import SELECTED_NEWS_FILE

ProgressCb = Callable[[str], None]

# ============================================================
# Configuration Constants
# ============================================================

MODEL_NAME = "claude-sonnet-4-6"
MAX_TOKENS = 2048
TEMPERATURE = 0.3

SYSTEM_PROMPT = (
    "You are a professional AI analyst specializing in Insurance and AI services. "
    "You write concise, structured, and business-oriented summaries in Korean."
)

USER_PROMPT_TEMPLATE = """
    <task>
    Analyze the following news article and produce a structured Korean output.

    <requirements>
    1. Generate [Summary1], [Summary2], ... [SummaryN] based on the article's content depth.
      - Do NOT attempt to summarize the entire article.
      - Focus on high-impact facts, decisions, or implications.
      - Default to 2 summaries, extend to 3 only if essential.
    2. Write ONE insight sentence for an insurance company use case.
    3. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
    4. Use professional Korean business tone.
    5. For [Title], use the original title provided below EXACTLY as-is. Do NOT modify, translate, or rephrase it.
    6. For [Summary], [Insight], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
    7. In insight, when referring to "our company" in Korean, use "당사".
    8. Please write each [Summary] and [Insight] between 100 and 200 characters.
    9. Avoid redundancy: [Title], [Summary], and [Insight] must each contain unique information without overlapping content or repeating the same expressions.

    <original_title>
    {title}

    <output_format>
    [Title]
    (Copy the original title exactly as provided above. Do not change anything.)

    [Summary1]
    First key point (e.g., new service/product and its features)

    [Summary2]
    Second key point (e.g., AI technologies applied) - if applicable

    [Summary3]
    - if applicable

    ... (continue as needed)

    [Insight]
    Suggest a concrete way this service or technology could be applied in our insurance company, along with expected benefits if applicable.
    (e.g., underwriting, claims, customer service, sales, marketing, risk management).

    <article>
    {content}
    """

# ============================================================
# Functions
# ============================================================

# Summarize Article Content
def summarize_article(title: str, content: str) -> Optional[str]:
    if not content or len(content.strip()) < 50:
        print("      ⚠️ 콘텐츠가 없거나 너무 짧습니다 (최소 50자 필요).")
        return None

    if " - " in title:
        title = title.split(" - ")[0].strip()

    return call_llm(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT_TEMPLATE.format(title=title, content=content),
        model=MODEL_NAME,
        max_tokens=MAX_TOKENS,
        log_prefix="      ",
    )


# Generate per-article summaries without user interaction. Returns list of
# {"index": int, "title": str, "summary": str}. Failed rows are skipped.
def generate_summaries(
    df: pd.DataFrame,
    progress_cb: ProgressCb = print,
) -> list[dict]:
    if df.empty:
        progress_cb("⚠️ 요약할 기사가 없습니다.")
        return []

    all_summaries: list[dict] = []
    total = len(df)

    for pos, (_, row) in enumerate(df.iterrows(), start=1):
        progress_cb(f"  📝 요약 중... ({pos}/{total}) {row.get('title', 'N/A')[:40]}...")
        summary = summarize_article(row["title"], row["content"])

        if summary is None:
            progress_cb(f"      ⚠️ 해당 기사 요약 실패. 건너뜁니다.")
            continue

        all_summaries.append({
            "index": pos,
            "title": row.get("title", "N/A"),
            "summary": summary,
        })

    return all_summaries


# Combine selected summaries into the final block of text passed to PPT.
def combine_summaries(summaries: list[dict], include_indices: list[int]) -> str:
    include = set(include_indices)
    return "\n\n".join(item["summary"] for item in summaries if item["index"] in include)


# CLI wrapper — interactive flow that prints summaries and asks the user
# which ones to combine.
def summarize_articles(df: pd.DataFrame) -> Optional[str]:
    all_summaries = generate_summaries(df)
    if not all_summaries:
        print("\n❌ 모든 기사 요약이 실패했습니다. 프로세스를 종료합니다.")
        return None

    print("\n" + "="*60)
    print("📋 전체 요약 결과")
    print("="*60)

    for item in all_summaries:
        print(f"\n[{item['index']}] {item['title'][:50]}...")
        print("-"*40)
        print(item['summary'])
        print()

    print("="*60)
    print("1개 이상의 포함할 요약 번호를 띄어쓰기로 구분하여 입력하세요. (예: 1 3 5)")
    print("="*60)

    while True:
        try:
            selection = input("선택: ").strip()

            if not selection:
                print("❌ 입력이 비어있습니다. 다시 입력해주세요.")
                continue

            selected_indices = [int(x) for x in selection.split()]

            invalid_indices = [idx for idx in selected_indices if idx < 1 or idx > len(all_summaries)]
            if invalid_indices:
                print(f"❌ 잘못된 번호가 포함되어 있습니다: {invalid_indices}")
                print(f"   유효한 범위: 1 ~ {len(all_summaries)}")
                continue

            if not selected_indices:
                print("❌ 최소 1개 이상의 요약을 선택해야 합니다.")
                continue

            break

        except ValueError:
            print("❌ 잘못된 입력입니다. 숫자만 입력해주세요. (예: 1 3 5)")
            continue

    combined = combine_summaries(all_summaries, selected_indices)
    print(f"\n✅ {len(selected_indices)}개 요약이 선택되었습니다!")
    return combined


# Test (If needed)
if __name__ == "__main__":

    df = pd.read_excel(SELECTED_NEWS_FILE, engine='openpyxl')
    if not df.empty:
        result = summarize_articles(df)
        print("\n" + "="*60)
        print("📋 최종 선택된 요약:")
        print("="*60)
        print(result)