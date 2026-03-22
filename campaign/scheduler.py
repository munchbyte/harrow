"""
campaign/scheduler.py — HARROW Autonomous Follow-Up Scheduler.

Once GO is granted, HARROW owns the full email sequence without further
input from Adrian. M2 and M3 are automatic continuations.

check_and_send_followups() — called on schedule (every hour, Mon-Fri 08:00-17:00):
- Stage 1, 5+ days since M1, no reply -> send M2, advance to stage 2
- Stage 2, 5+ days since M2, no reply -> send M3, advance to stage 3
- Each send fires [HARROW->LOG_SYNC]
- Opt-out in reply -> stage -99, HITL gate, halt all sends

Started as asyncio background task on agent startup.
Logs WARN if GO not armed.
"""

# Phase 3: implement check_and_send_followups(), start_scheduler()
