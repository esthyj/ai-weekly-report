from .openai_client import get_shared_client
from .config import AILAB_CONTENT_FILE
from pathlib import Path
from openai import APIError, RateLimitError, APIConnectionError

# Get shared OpenAI client instance
client = get_shared_client()

# ============================================================
# Configuration Constants
# ============================================================

MODEL_NAME = "gpt-5.1"
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
    6. Please write [Summary1] and [Summary2] each within 150 characters

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

# Return AI Lab news summarization results
def ailab_summarized():

    # Check if AI Lab content file exists
    if not Path(AILAB_CONTENT_FILE).exists():
        print(f"❌ 오류: AI Lab 콘텐츠 파일을 찾을 수 없습니다: {AILAB_CONTENT_FILE}")
        print(f"   '{AILAB_CONTENT_FILE}' 파일을 생성하고 내용을 입력해주세요.")
        return None

    # Ailab Contents are saved in txt file
    try:
        with open(AILAB_CONTENT_FILE, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ AI Lab 콘텐츠 파일 읽기 실패: {e}")
        return None

    if not content or len(content.strip()) < 10:
        print(f"❌ AI Lab 콘텐츠 파일이 비어있거나 내용이 너무 짧습니다.")
        return None

    # OpenAI API call with error handling
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(content=content)
                }
            ],
            temperature=TEMPERATURE
        )

        # Validate response has choices
        if not response.choices or len(response.choices) == 0:
            print("❌ OpenAI API 응답이 비어있습니다.")
            return None

        result = response.choices[0].message.content.strip()
        return result

    except RateLimitError as e:
        print(f"❌ OpenAI API 요청 한도 초과: {e}")
        print("   잠시 후 다시 시도해주세요.")
        return None
    except APIConnectionError as e:
        print(f"❌ OpenAI API 연결 실패: {e}")
        print("   네트워크 연결을 확인해주세요.")
        return None
    except APIError as e:
        print(f"❌ OpenAI API 오류: {e}")
        return None
    except Exception as e:
        print(f"❌ 예상치 못한 오류 발생: {e}")
        return None


# Test (If needed)
if __name__ == "__main__":
    result = ailab_summarized()
    print(result)