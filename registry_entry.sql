-- HARROW — ASP-002 Agent Registry Entry
-- Run against the AIOS agent_registry database in Phase 6.

INSERT INTO agent_registry (
    agent_id,
    name,
    description,
    version,
    host,
    port,
    health_endpoint,
    status,
    capabilities,
    registered_at
) VALUES (
    'harrow',
    'HARROW — The Resonant CMO',
    'Chief Marketing Officer agent for Goblin Media Network / Attic Tech Solutions. '
    'Five channels: lead gen, email, voice, social, ads. '
    '7-stage Campaign Builder. Voss copy techniques. '
    'ASP-001/002/003 compliant. GMN Marketing Rules Charter v2.0.',
    '1.0.0',
    'harrow.goblinmedia.net',
    8001,
    '/health',
    'active',
    '["run_lead_harvest","run_ghost_audit","run_copy_review","run_voice_brief","run_social_brief","run_ads_brief","run_channel_report","run_campaign"]',
    datetime('now')
);
