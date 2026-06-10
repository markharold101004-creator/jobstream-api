#!/bin/bash
# JobStream restart script - starts Flask API + Cloudflare tunnel
# Run manually or via @reboot cron

echo "[$(date)] Starting JobStream services..."

# Kill old processes
kill $(cat /tmp/flask_pid 2>/dev/null) 2>/dev/null
kill $(cat /tmp/cloudflared_pid 2>/dev/null) 2>/dev/null
sleep 1

# Start Flask
cd /root/jobscraper
source venv/bin/activate
nohup python app.py > /tmp/app.log 2>&1 &
echo $! > /tmp/flask_pid
echo "Flask started (PID: $(cat /tmp/flask_pid))"
sleep 3

# Start Cloudflare tunnel
nohup /usr/local/bin/cloudflared tunnel --url http://localhost:8080 --no-autoupdate > /tmp/cloudflared.log 2>&1 &
echo $! > /tmp/cloudflared_pid
echo "Cloudflared started (PID: $(cat /tmp/cloudflared_pid))"

# Wait for tunnel URL
TUNNEL_URL=""
for i in $(seq 1 20); do
    sleep 2
    TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
done

if [ -z "$TUNNEL_URL" ]; then
    echo "ERROR: Could not get tunnel URL"
    exit 1
fi

echo "Tunnel URL: $TUNNEL_URL"
echo "$TUNNEL_URL" > /tmp/jobstream_url.txt

# Restart Flask with correct BASE_URL
kill $(cat /tmp/flask_pid 2>/dev/null) 2>/dev/null
sleep 1
cd /root/jobscraper
export BASE_URL=$TUNNEL_URL
nohup python app.py > /tmp/app.log 2>&1 &
echo $! > /tmp/flask_pid
echo "Flask restarted with BASE_URL=$TUNNEL_URL (PID: $(cat /tmp/flask_pid))"
sleep 3

# Update Stripe webhook
source /root/jobscraper/.env 2>/dev/null
if [ -z "$STRIPE_SECRET_KEY" ]; then echo "WARNING: STRIPE_SECRET_KEY not set, skipping webhook update"; else
source venv/bin/activate && python -c "
import stripe, os
stripe.api_key = os.environ['STRIPE_SECRET_KEY']
for ep in stripe.WebhookEndpoint.list():
    stripe.WebhookEndpoint.modify(ep.id, url='$TUNNEL_URL/api/stripe-webhook')
    print(f'Webhook updated -> $TUNNEL_URL/api/stripe-webhook')
" 2>&1
fi

# Verify
echo "Verifying..."
source venv/bin/activate && python -c "
import requests
r1 = requests.get('http://localhost:8080/', timeout=5)
r2 = requests.get('$TUNNEL_URL/', timeout=10)
r3 = requests.post('$TUNNEL_URL/api/register', json={'email': 'test@example.com'}, timeout=10)
print(f'Local: {r1.status_code}, Tunnel: {r2.status_code}, Register: {r3.status_code} ({r3.json().get(\"plan\", \"\")})')
r4 = requests.get('$TUNNEL_URL/api/jobs/stats?api_key=' + r3.json().get('api_key', ''), timeout=10)
data = r4.json()
print(f'Stats: {r4.status_code} - {data.get(\"total_jobs\", 0)} jobs from {list(data.get(\"sources\", {}).keys())}')
"

echo ""
echo "=== JobStream is LIVE ==="
echo "URL:  $TUNNEL_URL"
echo "Docs: $TUNNEL_URL/docs"
echo "API:  $TUNNEL_URL/api/jobs?api_key=YOUR_KEY"
