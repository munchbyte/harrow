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

# Phase 2: implement call_claude(), call_haiku(), call_sonnet()
