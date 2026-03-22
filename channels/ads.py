"""
channels/ads.py — HARROW Paid Ads Channel.

Generates ad campaign briefs via Claude Sonnet.
Budget hard ceiling check. HITL gate fires before returning — always.

Output: audience, ad_copy (headline1, headline2, description, CTA),
KPIs, engine_layer, dashboard_layer.

Task: task_ads_brief(job_id, params, caller)
Params: platform, campaign_type, objective, target_sector, monthly_budget_gbp
"""

# Phase 4: implement task_ads_brief()
