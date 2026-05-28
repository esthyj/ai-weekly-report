from typing import Optional

from .llm_client import call_llm

# ============================================================
# Configuration Constants
# ============================================================

MODEL_NAME = "claude-sonnet-4-6"
MAX_TOKENS = 1024
TEMPERATURE = 0.3

SYSTEM_PROMPT = (
    "You are a professional AI analyst specializing in Insurance and AI services. "
    "You write concise, structured, and business-oriented summaries in Korean."
)

USER_PROMPT_TEMPLATE = """
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
    """

# ============================================================
# Functions
# ============================================================

def ailab_summarized(content: str) -> Optional[str]:
    """사용자가 직접 입력한 AI Lab 콘텐츠를 요약.

    `content`는 호출자(CLI 또는 웹 API)가 사용자 입력으로부터 수집해 전달.
    """
    if not content or len(content.strip()) < 10:
        print("❌ AI Lab 콘텐츠가 비어있거나 내용이 너무 짧습니다 (10자 이상 필요).")
        return None

    return call_llm(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT_TEMPLATE.format(content=content),
        model=MODEL_NAME,
        max_tokens=MAX_TOKENS,
    )


# Test (If needed)
if __name__ == "__main__":
    sample = input("AI Lab 콘텐츠 (테스트용 한 줄): ")
    result = ailab_summarized(sample)
    print(result)
