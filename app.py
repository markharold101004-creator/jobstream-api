#!/usr/bin/env python3
"""JobStream API — Live Job Listings Data. Sell API keys via Stripe."""
import json
import os
import secrets
from functools import wraps
from pathlib import Path

import stripe
from flask import Flask, jsonify, request, abort, make_response, redirect

app = Flask(__name__)

DATA_DIR = Path(__file__).parent / "data"
LIVE_FILE = DATA_DIR / "live_jobs.json"
KEYS_FILE = DATA_DIR / "api_keys.json"

API_KEYS = {}

# Stripe config — set these env vars after you create your Stripe account
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")

PLANS = {
    "starter": {"label": "Starter", "price_cents": 2900, "calls": 1_000},
    "pro": {"label": "Pro", "price_cents": 9900, "calls": 10_000},
    "enterprise": {"label": "Enterprise", "price_cents": 29900, "calls": 100_000},
}


def load_api_keys():
    if KEYS_FILE.exists():
        with open(KEYS_FILE) as f:
            API_KEYS.update(json.load(f))


def save_api_keys():
    with open(KEYS_FILE, "w") as f:
        json.dump(API_KEYS, f, indent=2)


def require_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if not key or key not in API_KEYS:
            abort(401, "Invalid or missing API key")
        return f(*args, **kwargs)
    return decorated


def load_jobs():
    if LIVE_FILE.exists():
        with open(LIVE_FILE) as f:
            return json.load(f)
    return []


# ---- Landing page ----
@app.route("/")
def index():
    resp = make_response(LANDING_HTML)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


# ---- API docs ----
@app.route("/docs")
def docs():
    resp = make_response(DOCS_HTML)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


# ---- Create Stripe Checkout Session ----
@app.route("/api/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    plan = data.get("plan", "starter")

    if plan not in PLANS:
        return jsonify({"error": "Invalid plan"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    p = PLANS[plan]

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            customer_email=email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"JobStream {p['label']}"},
                    "recurring": {"interval": "month"},
                    "unit_amount": p["price_cents"],
                },
                "quantity": 1,
            }],
            success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/",
            metadata={"plan": plan, "email": email},
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---- Stripe webhook (called by Stripe after payment) ----
@app.route("/api/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({"error": "Invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("metadata", {}).get("email", "")
        plan = session.get("metadata", {}).get("plan", "starter")
        _grant_api_key(email, plan)

    return jsonify({"status": "ok"})


# ---- Success page (user lands here after Stripe payment) ----
@app.route("/success")
def success():
    session_id = request.args.get("session_id", "")
    key = ""
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            email = session.get("metadata", {}).get("email", "")
            plan = session.get("metadata", {}).get("plan", "starter")
            key = _grant_api_key(email, plan)
        except Exception:
            pass

    html = SUCCESS_HTML.replace("__API_KEY__", key)
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


def _grant_api_key(email: str, plan: str) -> str:
    for k, v in API_KEYS.items():
        if v.get("email") == email and v.get("plan") == plan:
            return k
    key = secrets.token_urlsafe(32)
    p = PLANS.get(plan, PLANS["starter"])
    API_KEYS[key] = {"email": email, "plan": plan, "calls": 0, "calls_limit": p["calls"]}
    save_api_keys()
    return key


# ---- Free registration (for demo / waitlist) ----
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    key = secrets.token_urlsafe(32)
    API_KEYS[key] = {"email": email, "plan": "free", "calls": 0, "calls_limit": 100}
    save_api_keys()
    return jsonify({"api_key": key, "plan": "free"})


@app.route("/api/key-info")
@require_key
def key_info():
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    info = API_KEYS.get(key, {})
    return jsonify(info)


# ---- Job API endpoints ----
@app.route("/api/jobs")
@require_key
def get_jobs():
    jobs = load_jobs()
    q = request.args.get("q", "").lower()
    source = request.args.get("source", "").lower()
    limit = request.args.get("limit", type=int, default=100)

    if q:
        jobs = [j for j in jobs if q in j.get("title", "").lower()]
    if source:
        jobs = [j for j in jobs if j.get("source", "").lower() == source]

    return jsonify({"total": len(jobs), "results": jobs[:limit]})


@app.route("/api/jobs/stats")
@require_key
def get_stats():
    jobs = load_jobs()
    sources = {}
    for j in jobs:
        s = j.get("source", "unknown")
        sources[s] = sources.get(s, 0) + 1
    return jsonify({"total_jobs": len(jobs), "sources": sources})


LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JobStream API — Live Job Listings Data</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .gradient-text { background: linear-gradient(135deg, #6366f1, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .pricing-card:hover { transform: translateY(-4px); box-shadow: 0 20px 40px rgba(0,0,0,0.1); }
    .hero-gradient { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
  </style>
</head>
<body class="bg-slate-50" id="app">
  <div class="hero-gradient text-white">
    <div class="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
      <div class="text-xl font-bold"><span class="text-indigo-400">Job</span>Stream</div>
      <div class="flex gap-4 text-sm">
        <a href="/#features" class="hover:text-indigo-300 transition">Features</a>
        <a href="/#pricing" class="hover:text-indigo-300 transition">Pricing</a>
        <a href="/docs" class="hover:text-indigo-300 transition">API</a>
      </div>
    </div>
    <div class="max-w-5xl mx-auto px-6 py-24 text-center">
      <h1 class="text-5xl md:text-6xl font-extrabold leading-tight mb-6">
        Live Job Listings<br><span class="gradient-text">at Your Fingertips</span>
      </h1>
      <p class="text-xl text-slate-300 max-w-2xl mx-auto mb-10">
         One API. 400+ fresh jobs daily from 8 sources. Build job boards, power AI agents, or feed your analytics.
      </p>
      <div class="flex gap-4 justify-center flex-wrap">
        <a href="/#pricing" class="bg-indigo-500 hover:bg-indigo-600 text-white px-8 py-3 rounded-xl font-semibold transition shadow-lg shadow-indigo-500/25">Get Started</a>
        <a href="/docs" class="border border-slate-400 hover:border-white px-8 py-3 rounded-xl font-semibold transition">API Docs</a>
      </div>
    </div>
  </div>

  <div id="features" class="max-w-6xl mx-auto px-6 py-24">
    <h2 class="text-3xl font-bold text-center mb-4">Why JobStream?</h2>
    <p class="text-slate-500 text-center mb-16 max-w-xl mx-auto">Fresh, structured job data from the best remote and tech job boards</p>
    <div class="grid md:grid-cols-3 gap-8">
      <div class="bg-white rounded-2xl p-8 shadow-sm border border-slate-100">
        <div class="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center mb-5 text-2xl">&#x1F4E1;</div>
        <h3 class="text-lg font-bold mb-2">8 Sources & Growing</h3>
        <p class="text-slate-500 text-sm">RemoteOK, WeWorkRemotely, Remotive, The Muse, Himalayas, Workbeam, Career Nest, JobsBase — aggregated and deduped.</p>
      </div>
      <div class="bg-white rounded-2xl p-8 shadow-sm border border-slate-100">
        <div class="w-12 h-12 bg-cyan-100 rounded-xl flex items-center justify-center mb-5 text-2xl">&#x26A1;</div>
        <h3 class="text-lg font-bold mb-2">Real-time API</h3>
        <p class="text-slate-500 text-sm">JSON endpoints with search, filter by source, keyword, and location. Fast and reliable.</p>
      </div>
      <div class="bg-white rounded-2xl p-8 shadow-sm border border-slate-100">
        <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center mb-5 text-2xl">&#x1F4E6;</div>
        <h3 class="text-lg font-bold mb-2">CSV & JSON Export</h3>
        <p class="text-slate-500 text-sm">Download clean, deduplicated datasets. Build models, train AI, or analyze markets.</p>
      </div>
    </div>
  </div>

  <div id="pricing" class="max-w-5xl mx-auto px-6 py-24">
    <h2 class="text-3xl font-bold text-center mb-4">Simple Pricing</h2>
    <p class="text-slate-500 text-center mb-16 max-w-xl mx-auto">Start free, scale as you grow. No hidden fees.</p>
    <div class="grid md:grid-cols-3 gap-6">
      <div class="pricing-card bg-white rounded-2xl p-8 border border-slate-100 shadow-sm transition duration-200">
        <h3 class="text-lg font-bold mb-2">Starter</h3>
        <div class="text-4xl font-extrabold mb-1">$29<span class="text-base font-normal text-slate-400">/mo</span></div>
        <p class="text-sm text-slate-500 mb-6">For indie devs and side projects</p>
        <ul class="space-y-3 text-sm mb-8">
          <li class="flex gap-2">&#x2705; 1,000 API calls/mo</li>
          <li class="flex gap-2">&#x2705; 5 data sources</li>
          <li class="flex gap-2">&#x2705; Search & filter</li>
          <li class="flex gap-2">&#x2705; Email support</li>
        </ul>
        <button @click="checkout('starter')" class="w-full bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-xl font-semibold transition">Subscribe</button>
      </div>
      <div class="pricing-card bg-white rounded-2xl p-8 border-2 border-indigo-500 shadow-lg relative">
        <div class="absolute -top-3 left-1/2 -translate-x-1/2 bg-indigo-500 text-white text-xs font-bold px-4 py-1 rounded-full">Popular</div>
        <h3 class="text-lg font-bold mb-2">Pro</h3>
        <div class="text-4xl font-extrabold mb-1">$99<span class="text-base font-normal text-slate-400">/mo</span></div>
        <p class="text-sm text-slate-500 mb-6">For startups and growing teams</p>
        <ul class="space-y-3 text-sm mb-8">
          <li class="flex gap-2">&#x2705; 10,000 API calls/mo</li>
          <li class="flex gap-2">&#x2705; All sources + priority</li>
          <li class="flex gap-2">&#x2705; Full-text search</li>
          <li class="flex gap-2">&#x2705; CSV/JSON exports</li>
          <li class="flex gap-2">&#x2705; Slack support</li>
        </ul>
        <button @click="checkout('pro')" class="w-full bg-indigo-500 hover:bg-indigo-600 text-white py-3 rounded-xl font-semibold transition shadow-lg shadow-indigo-500/25">Subscribe</button>
      </div>
      <div class="pricing-card bg-white rounded-2xl p-8 border border-slate-100 shadow-sm transition duration-200">
        <h3 class="text-lg font-bold mb-2">Enterprise</h3>
        <div class="text-4xl font-extrabold mb-1">$299<span class="text-base font-normal text-slate-400">/mo</span></div>
        <p class="text-sm text-slate-500 mb-6">For companies at scale</p>
        <ul class="space-y-3 text-sm mb-8">
          <li class="flex gap-2">&#x2705; Unlimited API calls</li>
          <li class="flex gap-2">&#x2705; Custom data sources</li>
          <li class="flex gap-2">&#x2705; Dedicated support</li>
          <li class="flex gap-2">&#x2705; SLA guarantee</li>
          <li class="flex gap-2">&#x2705; White-label option</li>
        </ul>
        <button @click="checkout('enterprise')" class="w-full bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-xl font-semibold transition">Subscribe</button>
      </div>
    </div>
    <div class="text-center mt-10">
      <p class="text-slate-500 text-sm mb-2">Want to try before buying?</p>
      <button @click="showFreeSignup = true" class="text-indigo-500 hover:text-indigo-600 font-semibold">Get a free API key &rarr;</button>
    </div>
  </div>

  <!-- Email modal before Stripe redirect -->
  <div v-if="showEmailModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="showEmailModal = false">
    <div class="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl">
      <h3 class="text-2xl font-bold mb-2">Subscribe to {{checkoutPlan}}</h3>
      <p class="text-slate-500 text-sm mb-6">Enter your email to proceed to secure checkout.</p>
      <form @submit.prevent="doCheckout">
        <input v-model="checkoutEmail" type="email" placeholder="you@example.com" class="w-full border border-slate-200 rounded-xl px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-400" required>
        <button type="submit" class="w-full bg-indigo-500 hover:bg-indigo-600 text-white py-3 rounded-xl font-semibold transition" :disabled="checkoutLoading">
          {{checkoutLoading ? 'Redirecting...' : 'Pay with Stripe &darr;'}}
        </button>
      </form>
      <button @click="showEmailModal = false" type="button" class="mt-4 text-sm text-slate-400 hover:text-slate-600">Cancel</button>
    </div>
  </div>

  <!-- Free signup modal -->
  <div v-if="showFreeSignup" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="showFreeSignup = false">
    <div class="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl">
      <h3 class="text-2xl font-bold mb-2">Free API Key</h3>
      <p class="text-slate-500 text-sm mb-6">Get a free key with 100 calls/mo to evaluate.</p>
      <form @submit.prevent="register">
        <input v-model="email" type="email" placeholder="you@example.com" class="w-full border border-slate-200 rounded-xl px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-400" required>
        <button type="submit" class="w-full bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-xl font-semibold transition" :disabled="loading">
          {{loading ? 'Generating...' : 'Get Free Key'}}
        </button>
      </form>
      <div v-if="freeKey" class="mt-6 bg-slate-50 rounded-xl p-4">
        <p class="text-sm font-semibold text-green-600 mb-2">&#x2705; Your API Key:</p>
        <code class="block bg-slate-800 text-green-400 p-3 rounded-lg text-sm break-all">{{freeKey}}</code>
        <p class="text-xs text-slate-500 mt-2">Save this!</p>
      </div>
      <button @click="showFreeSignup = false" type="button" class="mt-4 text-sm text-slate-400 hover:text-slate-600">Close</button>
    </div>
  </div>

  <footer class="bg-slate-900 text-slate-400 py-12 text-center text-sm">
    <p class="font-bold text-white mb-2"><span class="text-indigo-400">Job</span>Stream API</p>
     <p>Built with data from RemoteOK, WeWorkRemotely, Remotive, The Muse, Himalayas, Workbeam, Career Nest, JobsBase</p>
    <p class="mt-2">&copy; 2026 JobStream. All rights reserved.</p>
  </footer>

  <script>
    const { createApp, ref } = Vue;
    createApp({
      setup() {
        const showEmailModal = ref(false);
        const checkoutPlan = ref('starter');
        const checkoutEmail = ref('');
        const checkoutLoading = ref(false);
        const showFreeSignup = ref(false);
        const email = ref('');
        const freeKey = ref('');
        const loading = ref(false);

        const checkout = (plan) => {
          checkoutPlan.value = plan;
          checkoutEmail.value = '';
          showEmailModal.value = true;
        };

        const doCheckout = async () => {
          checkoutLoading.value = true;
          try {
            const res = await fetch('/api/create-checkout-session', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({email: checkoutEmail.value, plan: checkoutPlan.value})
            });
            const data = await res.json();
            if (data.url) window.location.href = data.url;
            else alert('Error: ' + (data.error || 'Unknown'));
          } catch(e) {
            alert('Error: ' + e.message);
          } finally {
            checkoutLoading.value = false;
          }
        };

        const register = async () => {
          loading.value = true;
          try {
            const res = await fetch('/api/register', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({email: email.value})
            });
            const data = await res.json();
            if (data.api_key) freeKey.value = data.api_key;
          } catch(e) {
            alert('Error: ' + e.message);
          } finally {
            loading.value = false;
          }
        };

        return { showEmailModal, checkoutPlan, checkoutEmail, checkoutLoading, checkout, doCheckout, showFreeSignup, email, freeKey, loading, register };
      }
    }).mount('#app');
  </script>
</body>
</html>"""


SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Payment Successful — JobStream</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen p-4">
  <div class="bg-white rounded-2xl p-8 max-w-lg w-full shadow-lg text-center">
    <div class="text-5xl mb-4">&#x2705;</div>
    <h1 class="text-3xl font-bold mb-2">Payment Successful!</h1>
    <p class="text-slate-500 mb-6">Your subscription is active. Here's your API key:</p>
    <code class="block bg-slate-800 text-green-400 p-4 rounded-xl text-sm break-all mb-6">__API_KEY__</code>
    <p class="text-sm text-slate-500 mb-6">Save this key — you won't see it again. Use it to access the JobStream API.</p>
    <div class="flex gap-3 justify-center">
      <a href="/docs" class="bg-indigo-500 hover:bg-indigo-600 text-white px-6 py-3 rounded-xl font-semibold transition">View API Docs</a>
      <a href="/" class="border border-slate-300 hover:border-slate-400 px-6 py-3 rounded-xl font-semibold transition">Home</a>
    </div>
  </div>
</body>
</html>"""


DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JobStream API Docs</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="bg-slate-900 text-white">
  <div class="max-w-4xl mx-auto px-6 py-12">
    <a href="/" class="text-indigo-400 hover:underline text-sm">&larr; Back to home</a>
    <h1 class="text-4xl font-bold mt-6 mb-2">API Documentation</h1>
    <p class="text-slate-400 mb-10">Authenticate with your API key via <code class="bg-slate-800 px-2 py-1 rounded">?api_key=KEY</code> or <code class="bg-slate-800 px-2 py-1 rounded">X-API-Key</code> header.</p>

    <h2 class="text-2xl font-bold mt-10 mb-4">Endpoints</h2>

    <div class="bg-slate-800 rounded-xl p-6 mb-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="bg-green-500 text-black text-xs font-bold px-2 py-1 rounded">GET</span>
        <code class="text-lg">/api/jobs</code>
      </div>
      <p class="text-slate-300 mb-4">Get job listings with optional filters.</p>
      <table class="w-full text-sm">
        <thead><tr class="text-slate-400 border-b border-slate-700"><th class="text-left pb-2">Param</th><th class="text-left pb-2">Type</th><th class="text-left pb-2">Description</th></tr></thead>
        <tbody>
          <tr class="border-b border-slate-700"><td class="py-2">q</td><td>string</td><td>Search keyword in title</td></tr>
          <tr class="border-b border-slate-700"><td class="py-2">source</td><td>string</td><td>Filter by source (remoteok, weworkremotely, remotive, themuse, himalayas, workbeam, careernest, jobsbase)</td></tr>
          <tr><td class="py-2">limit</td><td>int</td><td>Max results (default 100)</td></tr>
        </tbody>
      </table>
      <pre class="bg-slate-900 p-4 rounded-xl text-sm mt-4 overflow-x-auto">curl "/api/jobs?q=engineer&source=remoteok&limit=5&api_key=KEY"</pre>
    </div>

    <div class="bg-slate-800 rounded-xl p-6 mb-6">
      <div class="flex items-center gap-3 mb-4">
        <span class="bg-green-500 text-black text-xs font-bold px-2 py-1 rounded">GET</span>
        <code class="text-lg">/api/jobs/stats</code>
      </div>
      <p class="text-slate-300 mb-4">Get dataset statistics.</p>
      <pre class="bg-slate-900 p-4 rounded-xl text-sm mt-4 overflow-x-auto">curl "/api/jobs/stats?api_key=KEY"</pre>
    </div>

    <footer class="mt-16 pt-8 border-t border-slate-700 text-center text-sm text-slate-500">
      <p>&copy; 2026 JobStream API</p>
    </footer>
  </div>
</body>
</html>"""


if __name__ == "__main__":
    load_api_keys()
    print(f"API keys loaded: {len(API_KEYS)}")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
