"""
engine/claude_client.py — HARROW Anthropic Claude API client.

Wraps the Anthropic SDK. Provides structured calls for:
- Copy generation (Sonnet 4.6)
- Gate checks (Haiku 4.5)
- Ghost Audit analysis (Haiku 4.5)
- Voice/Social/Ads brief generation (Sonnet 4.6)

Every call: try/except with ASP-003 stop-log-alert.
One timeout retry only. No retry on 4xx/5xx.
"""

import os
import json
from typing import Optional
from pathlib import Path

import anthropic

from core.logging import alog

# Model IDs
HAIKU = "claude-haiku-4-5-20250315"
SONNET = "claude-sonnet-4-6-20250514"

# Load system prompt from HARROW.md
_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "HARROW.md"
_SYSTEM_PROMPT: Optional[str] = None


def _get_system_prompt() -> str:
    """Load and cache the HARROW system prompt."""
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return _SYSTEM_PROMPT


def _get_client() -> anthropic.Anthropic:
    """Create a new Anthropic client. Raises if key not set."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=key, timeout=60.0)


async def call_claude(
    prompt: str,
    *,
    model: str = SONNET,
    system: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    job_id: Optional[str] = None,
    step: Optional[str] = None,
) -> str:
    """
    Call Claude with a single user message. Returns the text response.
    ASP-003: try/except, one timeout retry, log on failure.
    """
    if system is None:
        system = _get_system_prompt()

    client = _get_client()
    attempt = 0
    last_error = None

    while attempt < 2:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            text = response.content[0].text
            alog(
                "INFO",
                f"Claude {model.split('-')[1]} call OK ({response.usage.input_tokens}+{response.usage.output_tokens} tokens)",
                job_id=job_id, step=step or "claude_call",
                action=f"call_{model}", outcome="success",
            )
            return text

        except anthropic.APITimeoutError as e:
            last_error = e
            attempt += 1
            if attempt < 2:
                alog("WARN", f"Claude timeout, retrying (attempt {attempt})",
                     job_id=job_id, step=step or "claude_call")
                continue

        except anthropic.APIStatusError as e:
            # No retry on 4xx/5xx
            alog(
                "ERROR",
                f"Claude API error {e.status_code}: {e.message}. "
                f"To resolve this: check ANTHROPIC_API_KEY and request params",
                job_id=job_id, step=step or "claude_call",
                action=f"call_{model}", outcome=f"error_{e.status_code}",
            )
            raise

        except Exception as e:
            alog(
                "ERROR",
                f"Claude call failed: {type(e).__name__}: {e}. "
                f"To resolve this: check network and API key",
                job_id=job_id, step=step or "claude_call",
                action=f"call_{model}", outcome="error",
            )
            raise

    # Exhausted retries
    alog(
        "ERROR",
        f"Claude call failed after retry: {last_error}. "
        f"To resolve this: check network connectivity and Anthropic status",
        job_id=job_id, step=step or "claude_call",
        action=f"call_{model}", outcome="timeout",
    )
    raise last_error


async def call_haiku(
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 1024,
    job_id: Optional[str] = None,
    step: Optional[str] = None,
) -> str:
    """Call Claude Haiku for fast analysis tasks (gates, audit)."""
    return await call_claude(
        prompt, model=HAIKU, system=system,
        max_tokens=max_tokens, job_id=job_id, step=step,
    )


async def call_sonnet(
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 2048,
    job_id: Optional[str] = None,
    step: Optional[str] = None,
) -> str:
    """Call Claude Sonnet for generation tasks (copy, briefs)."""
    return await call_claude(
        prompt, model=SONNET, system=system,
        max_tokens=max_tokens, job_id=job_id, step=step,
    )


async def call_claude_json(
    prompt: str,
    *,
    model: str = HAIKU,
    system: Optional[str] = None,
    max_tokens: int = 1024,
    job_id: Optional[str] = None,
    step: Optional[str] = None,
) -> dict:
    """
    Call Claude and parse the response as JSON.
    Prompt should instruct Claude to return valid JSON only.
    """
    text = await call_claude(
        prompt, model=model, system=system,
        max_tokens=max_tokens, job_id=job_id, step=step,
    )
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        alog(
            "ERROR",
            f"Failed to parse Claude JSON response: {e}. To resolve this: check prompt for JSON instruction",
            job_id=job_id, step=step or "json_parse",
        )
        raise ValueError(f"Claude returned invalid JSON: {e}") from e
