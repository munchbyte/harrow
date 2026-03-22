"""
campaign/builder.py — HARROW 7-Stage Campaign Builder Orchestrator.

The Campaign Builder takes a sector, location, and tone from Adrian and
produces a complete, ready-to-send campaign in a single guided session.

Seven Stages:
1. Define — validate sector, location, limit, tone. Create campaign record.
2. Harvest — run Workflow A (Outscraper). ICP filter.
3. Audit — run Workflow B (Firecrawl + Claude) on all PASS leads.
4. Segment — group leads by Leak Type. Order by score. Flag WARNs.
5. Generate Copy — M1/M2/M3 per Leak Type. Five-Gate + Voss.
6. Review — HITL gate fires. Copy displayed for Adrian.
7. GO — Adrian approves. Email channel armed. Scheduler triggered.

Class: CampaignBuilder with .run(params) async method.
"""

# Phase 3: implement CampaignBuilder class
