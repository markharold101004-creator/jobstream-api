#!/bin/bash
# JobStream Watcher - keeps Flask + tunnel alive, auto-updates URL
# Runs from cron every 5 minutes

FLASK_PID=$(tmux list-sessions 2>/dev/null | grep flask | awk '{print $1}')
TUNNEL_PID=$(tmux list-sessions 2>/dev/null | grep cloudflare | awk '{print $1}')

# Check Flask
if ! curl -sf http://localhost:8080/ > /dev/null 2>&1; then
    echo "[$(date)] Flask is down. Restarting..."
    tmux kill-session -t flask 2>/dev/null
    tmux new-session -d -s flask "cd /root/jobscraper && source venv/bin/activate && python app.py"
    sleep 3
fi

# Check tunnel
TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log 2>/dev/null | head -1)
TUNNEL_OK=$(curl -sf "$TUNNEL_URL/" > /dev/null 2>&1 && echo 1 || echo 0)

if [ "$TUNNEL_OK" = "0" ]; then
    echo "[$(date)] Tunnel is down. Restarting..."
    tmux kill-session -t cloudflare 2>/dev/null
    sleep 1
    # Background cloudflared, capture logs
    nohup /usr/local/bin/cloudflared tunnel --url http://localhost:8080 --no-autoupdate > /tmp/cloudflared.log 2>&1 &
    CLOUDFLARED_PID=$!
    # Wait for URL
    for i in $(seq 1 15); do
        sleep 2
        TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log 2>/dev/null | head -1)
        if [ -n "$TUNNEL_URL" ]; then
            break
        fi
    done
    
    if [ -n "$TUNNEL_URL" ]; then
        echo "New tunnel URL: $TUNNEL_URL"
        # Update Stripe webhook
        source /root/jobscraper/.env 2>/dev/null
        if [ -n "$STRIPE_SECRET_KEY" ]; then
            source /root/jobscraper/venv/bin/activate && python -c "
import stripe, os
stripe.api_key = os.environ['STRIPE_SECRET_KEY']
for ep in stripe.WebhookEndpoint.list():
    stripe.WebhookEndpoint.modify(ep.id, url='$TUNNEL_URL/api/stripe-webhook')
    print(f'Webhook -> $TUNNEL_URL/api/stripe-webhook')
" 2>&1 | tee -a /tmp/jobstream-watcher.log
        fi
        
        # Restart Flask with new URL
        tmux kill-session -t flask 2>/dev/null
        sleep 1
        tmux new-session -d -s flask "cd /root/jobscraper && export BASE_URL=$TUNNEL_URL && source venv/bin/activate && python app.py"
        echo "Flask restarted with BASE_URL=$TUNNEL_URL"
    fi
fi

# Save tunnel URL to file for reference
echo "$(date) OK - $TUNNEL_URL" >> /tmp/jobstream-watcher.log 2>/dev/null
