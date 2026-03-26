"""
Shared Anthropic client configuration and initialization.
"""
import os
import httpx
import anthropic
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
