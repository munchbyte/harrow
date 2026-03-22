"""
core/hitl.py — HARROW HITL gate manager.

This is the ONLY place to fire HITL gates. Never inline gate logic.
Gates pause jobs at irreversible actions until human approval.

Hard stop conditions:
1. Stage 4/5 pipeline action
2. Outbound voice call brief
3. Social content publish
4. Paid ad campaign brief
5. New copy template — first live use
6. Reply with pricing/legal language
7. Enterprise tooling on site
8. Opt-out detected
9. 3-Failure Gate (DissonanceInquiry)

Also implements 3-Failure Gate tracking:
- track_rejection(output_type, job_id)
- On 3rd rejection: fire_dissonance_inquiry()
"""

# Phase 1: implement fire_hitl(), resolve_gate(), get_pending_gates()
# Phase 4: implement track_rejection(), fire_dissonance_inquiry()
