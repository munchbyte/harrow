# HARROW — VPS Deployment Guide

Target: Hostinger VPS at harrow.goblinmedia.net
Port: 8001 (internal), 443 (external via Nginx)

---

## Prerequisites
- Python 3.11+ installed on VPS
- Nginx installed
- Certbot installed
- Tailscale installed and authenticated
- Google service account JSON file on VPS
- All API keys ready (see .env.example)

---

## Step 1: Clone Repository
```bash
cd /var/www
git clone https://github.com/munchbyte/harrow.git
cd harrow
```

## Step 2: Environment
```bash
cp .env.example .env
nano .env  # Fill in all API keys and paths
```

## Step 3: Install Dependencies
```bash
pip install -r requirements.txt --break-system-packages
```

## Step 4: Verify Agent Starts
```bash
cd /var/www/harrow
python -m uvicorn harrow_agent:app --host 0.0.0.0 --port 8001
# Test: curl http://localhost:8001/health
# Ctrl+C to stop
```

## Step 5: systemd Service
```bash
cp harrow_agent.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable harrow-agent
systemctl start harrow-agent
systemctl status harrow-agent  # Confirm: active (running)
```

## Step 6: Nginx Reverse Proxy
```bash
cp nginx_harrow.conf /etc/nginx/sites-available/harrow
ln -s /etc/nginx/sites-available/harrow /etc/nginx/sites-enabled/
nginx -t  # Confirm: syntax is ok
systemctl reload nginx
```

## Step 7: SSL Certificate
```bash
certbot --nginx -d harrow.goblinmedia.net
```

## Step 8: Verify
```bash
curl https://harrow.goblinmedia.net/health
# Expected: {"status":"ok","agent_id":"harrow","timestamp":"...","data":{"version":"1.0.0","uptime_seconds":...}}
```

## Step 9: Tailscale Restriction
Uncomment the `allow` and `deny` lines in nginx_harrow.conf to restrict access to Tailscale network only.
```bash
nano /etc/nginx/sites-available/harrow
# Uncomment: allow 100.64.0.0/10;
# Uncomment: deny all;
nginx -t && systemctl reload nginx
```

## Step 10: Register in AIOS
```bash
# Run registry_entry.sql against the AIOS agent_registry database
sqlite3 /path/to/aios/agent_registry.db < registry_entry.sql
```

---

## Common Operations

### Restart Agent
```bash
systemctl restart harrow-agent
```

### View Logs
```bash
journalctl -u harrow-agent -f
```

### Update Code
```bash
cd /var/www/harrow
git pull origin main
systemctl restart harrow-agent
```

### Rotate API Key
Update HARROW_API_KEY in .env, then:
```bash
systemctl restart harrow-agent
# All existing dashboard sessions are invalidated
```

---

## Backup
```bash
# Database backup — one file
cp /var/www/harrow/state/harrow.db /backups/harrow_$(date +%Y%m%d).db
```
