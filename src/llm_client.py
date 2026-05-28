"""
Shared Anthropic client configuration and initialization.
"""
import os
from typing import Optional

import anthropic
import httpx
from dotenv import load_dotenv


def get_claude_client() -> anthropic.Anthropic:
    """
    Initialize and return an Anthropic client with configured settings.

    Returns:
        anthropic.Anthropic: Configured Anthropic client instance
    """
    load_dotenv()

    # Create HTTP client with SSL verification disabled
    # WARNING: Disabling SSL verification is a security risk
    # Consider enabling it in production environments
    http_client = httpx.Client(verify=False)

    # Initialize Anthropic client
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        http_client=http_client
    )

    return client


# Create a singleton instance for reuse across modules
_client_instance = None


def get_shared_client() -> anthropic.Anthropic:
    """
    Get or create a shared Anthropic client instance.

    Returns:
        anthropic.Anthropic: Shared Anthropic client instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = get_claude_client()
    return _client_instance


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_tokens: int,
    log_prefix: str = "",
) -> Optional[str]:
    """Single-shot Claude call with shared error handling. Returns text or None."""
    try:
        response = get_shared_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        if not response.content or len(response.content) == 0:
            print(f"{log_prefix}❌ Claude API 응답이 비어있습니다.")
            return None

        return response.content[0].text.strip()

    except anthropic.RateLimitError as e:
        print(f"{log_prefix}❌ Claude API 요청 한도 초과: {e}")
        print(f"{log_prefix}   잠시 후 다시 시도해주세요.")
        return None
    except anthropic.APIConnectionError as e:
        print(f"{log_prefix}❌ Claude API 연결 실패: {e}")
        print(f"{log_prefix}   네트워크 연결을 확인해주세요.")
        return None
    except anthropic.APIError as e:
        print(f"{log_prefix}❌ Claude API 오류: {e}")
        return None
    except Exception as e:
        print(f"{log_prefix}❌ 예상치 못한 오류 발생: {e}")
        return None
