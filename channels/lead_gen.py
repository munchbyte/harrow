"""
channels/lead_gen.py — HARROW Lead Generation (Workflows A + B).

Workflow A: Lead Harvest
- Outscraper Google Maps scraping + email enrichment
- ICP filter: hard rejects and soft warns
- Results written to Google Sheets Master Lead Sheet

Workflow B: Ghost Audit
- Firecrawl website scraping
- Claude Haiku analysis per lead
- Returns: leak_score (1-10), leak_type, leak_label
- Integrates Liability Predictor for niche-specific failure context

ICP Hard Rejects: no website, no phone, reviews >500, reviews <3, permanently closed
ICP Soft Warns: rating <2.5, reviews <10, no email, enterprise-hint keywords

Six Leak Types: BOOKING, CONTACT, SPEED, TRUST, CONTENT, NONE
"""

# Phase 2: implement task_lead_harvest(), task_ghost_audit()
