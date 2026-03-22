"""
channels/email.py — HARROW Email Channel.

Copy generation and review for M1/M2/M3 email sequences.
Uses Sonnet 4.6 for generation, Haiku 4.5 for gate checks.

Prompt includes: leak_type, leak_label, liability_context, sector, business_name, tone.
Each generated message has Sovereignty Footer appended automatically.

Tasks:
- task_copy_review(job_id, params, caller) — Five-Gate + Voss check on supplied copy_text
- generate_email_sequence(lead) — generate M1/M2/M3 for one lead
"""

# Phase 2: implement task_copy_review(), generate_email_sequence()
