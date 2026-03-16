"""
Shared Gemini client factory for AI Doc Generator.

All modules must import the Gemini client from here — never create
a raw `genai.Client()` inline. This ensures:
  - A single connection pool across the entire process.
  - Retry logic is applied consistently on every API call.
  - The client is only constructed once (lru_cache singleton).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from google import genai
from google.api_core import exceptions as google_exceptions
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from config import settings

logger = logging.getLogger("clients")

# ---------------------------------------------------------------------------
# Retry policy — applied to any function decorated with @gemini_retry
# ---------------------------------------------------------------------------

#: Exceptions that are safe to retry (transient server-side errors).
_RETRYABLE = (
    google_exceptions.ResourceExhausted,   # 429 quota
    google_exceptions.ServiceUnavailable,  # 503 transient
    google_exceptions.InternalServerError, # 500 transient
    google_exceptions.DeadlineExceeded,    # timeout
)

gemini_retry = retry(
    retry=retry_if_exception_type(_RETRYABLE),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""
Decorator that retries on transient Gemini API errors with exponential back-off.

Usage::

    @gemini_retry
    def call_llm(...) -> str:
        return client.models.generate_content(...)
"""


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_gemini_client() -> genai.Client:
    """
    Return the shared, process-wide Gemini client.

    The client is created once and cached for the lifetime of the process.
    Raises ``ValueError`` if the API key is not configured (caught early by
    the ``Settings`` validator in ``config.py``).

    Returns:
        A configured :class:`google.genai.Client` instance.
    """
    api_key = settings.gemini_api_key or ""
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=api_key)
