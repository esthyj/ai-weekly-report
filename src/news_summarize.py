import pandas as pd
from typing import Optional
from .openai_client import get_shared_client
from .config import SELECTED_NEWS_FILE
import anthropic

# Get shared Anthropic client instance
client = get_shared_client()

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

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(title=title, content=content)
                }
            ]
        )

        # Validate response has content
        if not response.content or len(response.content) == 0:
            print("      ❌ Claude API 응답이 비어있습니다.")
            return None

        return response.content[0].text.strip()

    except anthropic.RateLimitError as e:
        print(f"      ❌ Claude API 요청 한도 초과: {e}")
        print("         잠시 후 다시 시도해주세요.")
        return None
    except anthropic.APIConnectionError as e:
        print(f"      ❌ Claude API 연결 실패: {e}")
        print("         네트워크 연결을 확인해주세요.")
        return None
    except anthropic.APIError as e:
        print(f"      ❌ Claude API 오류: {e}")
        return None
    except Exception as e:
        print(f"      ❌ 예상치 못한 오류 발생: {e}")
        return None


# Summarize the articles in the DataFrame and return a combined string
def summarize_articles(df: pd.DataFrame) -> Optional[str]:
    if df.empty:
        print("⚠️ 요약할 기사가 없습니다.")
        return None
    
    all_summaries = []
    total = len(df)
    
    # 1단계: 모든 기사 요약
    for idx, row in df.iterrows():
        print(f"  📝 요약 중... ({idx + 1}/{total}) {row.get('title', 'N/A')[:40]}...")
        summary = summarize_article(row["title"], row["content"])

        # Handle API errors (summarize_article returns None on error)
        if summary is None:
            print(f"      ⚠️ 해당 기사 요약 실패. 건너뜁니다.")
            continue

        all_summaries.append({
            "index": idx + 1,
            "title": row.get("title", "N/A"),
            "summary": summary
        })
    
    # Check if any summaries were successfully generated
    if not all_summaries:
        print("\n❌ 모든 기사 요약이 실패했습니다. 프로세스를 종료합니다.")
        return None

    # 2단계: 전체 결과 출력
    print("\n" + "="*60)
    print("📋 전체 요약 결과")
    print("="*60)
    
    for item in all_summaries:
        print(f"\n[{item['index']}] {item['title'][:50]}...")
        print("-"*40)
        print(item['summary'])
        print()
    
    # 3단계: 사용자 선택 (띄어쓰기 기반)
    print("="*60)
    print("1개 이상의 포함할 요약 번호를 띄어쓰기로 구분하여 입력하세요. (예: 1 3 5)")
    print("="*60)

    while True:
        try:
            selection = input("선택: ").strip()

            if not selection:
                print("❌ 입력이 비어있습니다. 다시 입력해주세요.")
                continue

            selected_indices = {int(x) for x in selection.split()}

            # Validate that all indices are within valid range
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

    # 4단계: 선택된 것만 결합
    results = [
        item['summary']
        for item in all_summaries
        if item['index'] in selected_indices
    ]

    combined = "\n\n".join(results)
    print(f"\n✅ {len(results)}개 요약이 선택되었습니다!")

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