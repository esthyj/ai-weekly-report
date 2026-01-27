"""
Shared OpenAI client configuration and initialization.
"""
import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv


def get_openai_client() -> OpenAI:
    """
    Initialize and return an OpenAI client with configured settings.

    Returns:
        OpenAI: Configured OpenAI client instance
    """
    load_dotenv()

    # Create HTTP client with SSL verification disabled
    # WARNING: Disabling SSL verification is a security risk
    # Consider enabling it in production environments
    http_client = httpx.Client(verify=False)

    # Initialize OpenAI client
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        http_client=http_client
    )

    return client


# Create a singleton instance for reuse across modules
_client_instance = None


def get_shared_client() -> OpenAI:
    """
    Get or create a shared OpenAI client instance.

    Returns:
        OpenAI: Shared OpenAI client instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = get_openai_client()
    return _client_instance
