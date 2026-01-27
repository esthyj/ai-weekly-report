from .openai_client import get_shared_client
from .config import AILAB_CONTENT_FILE

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
    3. Be concise and factual. Do NOT add information not mentioned or logically implied in the article.
    4. Use professional Korean business tone.
    5. For [Title], Use noun-only endings
    6. For [Summary1], [Summary2], end sentences with noun-ending forms like "~임", "~함", "~있음" instead of formal endings like "~입니다", "~합니다", "~있습니다"
    8. Please write [Summary1] and [Summary2] each within 150 characters

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
    
    # Ailab Contents are saved in txt file
    with open(AILAB_CONTENT_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # OpenAI API call
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
    
    result = response.choices[0].message.content.strip()
    return result


# Test (If needed)
if __name__ == "__main__":
    result = ailab_summarized()
    print(result)