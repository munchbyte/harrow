"""
integrations/ — HARROW outbound clients to other sovereign agents.

One module per sub-agent. Each client wraps that agent's ASP-002 contract
(/health, /info, /run, /status, /logs, /stop) behind an async surface,
matching HARROW's existing convention of async public functions wrapping
sync IO (see engine/claude_client.py).
"""
