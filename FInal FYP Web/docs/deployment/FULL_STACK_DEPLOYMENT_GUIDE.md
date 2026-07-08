# VousFin — Complete Deployment Guide (Full Stack, Pilot-Ready for ~20 Testers)

This supersedes the scope of `DEPLOYMENT_GUIDE.md` (which only covered the main Node app). This guide covers **everything** that makes up VousFin — the main app, the 6 Python/TS microservices, ML/observability infra, and every external paid API — sized and priced for launching a private pilot to ~20 accountants at light-to-moderate daily use, with a clear path to scale beyond that.

Prices are best-known estimates — **verify on each provider's current pricing page before committing**.

---

## 1. What "VousFin" actually consists of (full inventory)

There are **three tiers**, not one:

### Tier A — The main app (what almost everything runs on today)
| Component | What it is |
|---|---|
| `vousfin-backend-main` | Node/Express API — the accounting engine, ledger, reports, AI assistant (DeepSeek) |
| `vousfin-frontend-main` | React SPA |

### Tier B — The FR-01 "Autonomous Transaction Engine" microservices (Docker, not yet confirmed deployed anywhere)
| Service | Language | Purpose | ML? |
|---|---|---|---|
| `ingestion-gateway` (port 8001) | Python/FastAPI | Front door for bank feeds/CSV imports — dedup, raw store, routes to the classifier | No (pandas/rules) |
| `ocr-service` (port 8002) | Python/FastAPI | Reads receipt/bill images/PDFs → structured data | Azure Form Recognizer (primary) + OpenAI GPT-4o Vision (fallback) |
| `classifier-service` (port 8003) | Python/FastAPI + Celery | Classifies/auto-posts transactions; trains & serves its own model | **Yes** — scikit-learn/XGBoost (gradient boosting, **CPU-only, no GPU needed**), tracked in MLflow |
| `reconciliation-service` (port 8004) | Python/FastAPI | Fuzzy-matches bank lines to ledger entries | No (statistical matching, not a trained model) |
| `bot-adapter` (port 8005) | Node/TypeScript | WhatsApp (Twilio) + Telegram bot front-ends for ingestion | No |
| `email-parser` | Python | Parses forwarded bill emails (IMAP) → sends to ingestion-gateway | No |

### Tier C — Shared infrastructure + external paid APIs
| Item | Used by | Cost driver |
|---|---|---|
| MongoDB | Everything | Storage + reads/writes |
| Redis | ingestion-gateway, classifier, reconciliation, email-parser (Celery + pub/sub) | Required for Tier B — not optional the way it is for the main app |
| MLflow | classifier-service | Model registry/tracking — self-hosted, no external cost |
| **DeepSeek** | Main app (already migrated) | Pay-per-token, ~$2–5/month at pilot scale |
| **Azure AI Form Recognizer** | ocr-service | Pay-per-page (~$1.50 per 1,000 pages on the Free/S0 tier's paid overage — first 500 pages/month are free) |
| **Azure Blob Storage** | ocr-service (stores the receipt images) | ~$0.02/GB/month — trivial at pilot scale |
| **OpenAI API** | ocr-service (vision fallback), bot-adapter | Separate from DeepSeek — pay-per-token, only used when Form Recognizer confidence is low |
| **Twilio** | bot-adapter (WhatsApp only) | ~$1–5/month number rental + ~$0.005–0.01/message — **optional, skip for launch** |
| Telegram Bot API | bot-adapter | Free |
| IMAP mailbox | email-parser | Free (use a Gmail address + app password) |

> **Honest flag:** Tier B is real, substantial code (6 services, real ML training/serving pipeline) but I found no evidence it's currently deployed anywhere — the frontend's queue/exception pages point at `localhost:8001-8004` by default. Treat Tier B as **"built but not yet live."** Decide in §2 whether to launch the pilot with or without it.

---

## 2. Should the pilot launch with Tier B on day one?

**Recommendation: launch Tier A alone first, add Tier B in week 2–3.** Reasoning:
- Tier A (the main app) is what 90% of an accountant's daily workflow touches — books, reports, invoices, the AI assistant. It's proven, tested, already live.
- Tier B adds real value (auto-classify bank feeds, WhatsApp/email bill capture) but is unverified in a deployed setting and pulls in 4 more paid external APIs (Azure ×2, OpenAI, optionally Twilio) that need their own accounts/keys before anything works.
- Shipping Tier A alone gets 20 testers using real accounting workflows **this week**; Tier B can follow once you've smoke-tested it yourself.

If you want Tier B live for day one anyway, everything below still applies — just do Steps 1–7 (Tier A) and Steps 8–13 (Tier B) together instead of in two waves.

---

## 3. Platform recommendation (replacing "just Vercel")

Vercel is serverless — it **cannot** run Tier B (Celery workers, long-lived Redis connections, a persistent MLflow server). You need a platform that runs Docker containers continuously. Two good options, in order of recommendation:

### 🥇 Recommended: Railway (railway.app)
- Deploys each service straight from its Dockerfile — no changes needed to the existing `docker-compose.yml` layout (Railway reads Docker builds natively; you add one Railway "service" per container).
- **Usage-based billing** (pay for actual CPU/RAM-seconds used) — at 20 light-moderate users, the whole Tier B stack realistically costs **$15–30/month total**, not per-service.
- Built-in Redis plugin (one click, no separate signup), private networking between services, environment variable groups shared across services, automatic HTTPS.
- Scales up smoothly later — no re-platforming needed to go from 20 to 2,000 users; you just raise the resource limits or add replicas.
- **This is the platform to use.**

### 🥈 Alternative (cheapest fixed cost, more hands-on): a single DigitalOcean Droplet
- One $24/month droplet (4GB RAM / 2 vCPU) running the **existing `docker-compose.yml` almost unchanged** (point `MONGO_URI` at Atlas instead of the local `mongo` container; keep the `redis` container local).
- Put **Caddy** (free, automatic HTTPS, ~10 lines of config) in front to reverse-proxy each service's port to a subdomain (e.g., `ocr.yourdomain.com → :8002`).
- Cheaper at fixed low usage, but you own patching, restarts, and monitoring yourself.
- Scale path: resize the droplet, or later split services onto DigitalOcean's managed Kubernetes (DOKS) once you outgrow one box.

**Keep Vercel for the frontend** either way — it's free, fast, and there's no reason to move it. If you go the Droplet route, you can optionally also move the main Node backend there for one consolidated bill, or leave it on Vercel (also fine — the two are independent).

---

## 4. Storage recommendation

`ocr-service` already writes receipt images to Azure Blob Storage (`blob_store.py`) — **keep it, zero code changes needed**, and it's genuinely cheap: at 20 accountants scanning maybe 5–10 receipts/day, you're storing a few GB/month → **under $1/month**.

If you later want to reduce how many different cloud vendors you depend on, **Cloudflare R2** is a drop-in S3-compatible alternative (10GB free, then $0.015/GB/month, **zero egress fees** — Azure charges for egress) — but that requires a small code change in `blob_store.py`. Not needed for launch; revisit only if vendor sprawl becomes annoying.

---

## 5. What to skip for the pilot (cut cost + complexity)

| Skip for now | Why | Add back when |
|---|---|---|
| **Twilio / WhatsApp bot** | Paid, needs business number verification, adds days of setup | Testers specifically ask for WhatsApp capture |
| **Prometheus + Grafana** | Pure observability, not needed to function | You have real usage data worth graphing (post-pilot) |
| MongoDB **Atlas M0 free tier** → use **M2 ($9/mo)** instead | M0 auto-pauses after inactivity and caps connections at 500 — looks broken to a real external tester if it's mid-nap when they log in | Never — M2/M5 is cheap enough to just keep |

Keep everything else — DeepSeek, Azure Form Recognizer + Blob, OpenAI (vision fallback only), Telegram bot, email-parser, MLflow (it's just one more lightweight container).

---

## 6. Pilot-scale cost summary (20 accountants, light-moderate daily use)

| Item | Platform | Monthly cost |
|---|---|---|
| Frontend | Vercel Hobby | $0 |
| Main backend | Vercel Hobby | $0 |
| Database | MongoDB Atlas M2 | ~$9 |
| Tier B (5 services + Redis + MLflow) | Railway | ~$15–30 |
| DeepSeek (main app AI) | pay-per-token | ~$2–5 |
| Azure Form Recognizer | pay-per-page (first 500 pages/mo free) | ~$0–5 |
| Azure Blob Storage | pay-per-GB | <$1 |
| OpenAI (vision fallback only — used rarely) | pay-per-token | ~$1–3 |
| Email (Brevo) | free tier | $0 |
| Cron (cron-job.org) | free | $0 |
| Telegram bot | free | $0 |
| **Total** | | **≈ $30–55/month** |

That's the full, real, "looks and runs like a product" cost for a 20-tester pilot — not the bare-bones $0 setup from the first guide, but still genuinely cheap for something you're putting in front of real accountants.

---

## 7. Step-by-step: Tier A (do this first)

Follow **`DEPLOYMENT_GUIDE.md`** Steps 1–7 exactly (Atlas, Brevo, DeepSeek, Vercel backend + frontend, cron-job.org) — just use an **Atlas M2 cluster** instead of M0 this time (Atlas → your cluster → "Edit configuration" → M2, ~$9/month).

---

## 8. Step-by-step: Tier B on Railway

### Step 8.1 — Create the Railway project
1. Sign up at **railway.app** (GitHub login is easiest).
2. New Project → **Deploy from GitHub repo** — point it at wherever `services/` lives (it can be a subfolder of a monorepo; Railway lets you set a build root per service).
3. You'll add **6 services** inside this one project: `ingestion-gateway`, `ocr-service`, `classifier-service`, `reconciliation-service`, `bot-adapter`, `email-parser`, plus a **Redis** plugin and an **MLflow** service.

### Step 8.2 — Add Redis
1. In the project → **New → Database → Redis** (one click, Railway manages it).
2. Note the connection variable Railway generates (`REDIS_URL`) — reference it in every service's env vars as `${{Redis.REDIS_URL}}` (Railway's variable-referencing syntax).

### Step 8.3 — Add MLflow
1. **New → Empty Service** → set it to deploy the `ghcr.io/mlflow/mlflow:v2.16.0` Docker image directly (Railway supports deploying a public image without a repo).
2. Start command: `mlflow server --host 0.0.0.0 --port 5000 --default-artifact-root /mlflow/artifacts`
3. Attach a Railway **volume** to `/mlflow` so trained models persist across restarts.
4. Note its internal URL — this becomes `MLFLOW_TRACKING_URI` for the classifier service.

### Step 8.4 — Add each Python/Node microservice
For **each** of `ingestion-gateway`, `ocr-service`, `classifier-service`, `reconciliation-service`, `email-parser`, `bot-adapter`:
1. **New → GitHub Repo** (same repo, different **root directory** set to `services/<name>`, since each already has its own `Dockerfile`).
2. Railway auto-detects the Dockerfile and builds it.
3. Add the environment variables from the table in §9 below (per service — not all services need all variables).
4. For `ingestion-gateway`, `ocr-service`, `classifier-service`, `reconciliation-service`: expose a **public domain** (Railway → Settings → Networking → Generate Domain) if the frontend needs to reach them directly, OR keep them **private** and instead have your main Node backend proxy requests to them (more secure, recommended once you're past the pilot — for now, public + JWT auth, matching how the frontend already calls them, is fine).
5. For `bot-adapter` and `email-parser`: these don't need public domains — they only make outbound calls to `ingestion-gateway`, keep them private.

### Step 8.5 — Wire the frontend to the real URLs
In your Vercel **frontend** project, set these to the Railway-generated public domains from Step 8.4 (replacing the `localhost:800x` defaults):
```
VITE_INGESTION_URL=https://ingestion-gateway-production-xxxx.up.railway.app
VITE_OCR_URL=https://ocr-service-production-xxxx.up.railway.app
VITE_CLASSIFIER_URL=https://classifier-service-production-xxxx.up.railway.app
VITE_RECONCILIATION_URL=https://reconciliation-service-production-xxxx.up.railway.app
```
Redeploy the frontend.

### Step 8.6 — Wire classifier-service back to the main backend
Set `VOUSFIN_API_URL` on the **classifier-service** Railway env to your **Vercel backend's** public URL (`https://your-backend.vercel.app`) — this is how AUTO_POST decisions actually get posted through the real, audited ledger engine, not a shadow copy.

---

## 9. Environment variables — who needs what

| Variable | ingestion-gateway | ocr-service | classifier-service | reconciliation-service | bot-adapter | email-parser |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `MONGO_URI` (Atlas) | ✅ | – | ✅ | ✅ | – | – |
| `MONGO_DB_NAME` | ✅ | – | ✅ | ✅ | – | – |
| `REDIS_URL` | ✅ | – | ✅ | ✅ | – | ✅ |
| `JWT_SECRET` (must match the Node backend's) | ✅ | – | – | – | – | – |
| `AZURE_FORM_RECOGNIZER_ENDPOINT` / `_KEY` | – | ✅ | – | – | – | – |
| `AZURE_STORAGE_CONNECTION_STRING` / `AZURE_BLOB_CONTAINER` | – | ✅ | – | – | – | – |
| `OPENAI_API_KEY` | – | ✅ | – | – | ✅ | – |
| `MLFLOW_TRACKING_URI` | – | – | ✅ | – | – | – |
| `VOUSFIN_API_URL` (main backend) | – | – | ✅ | – | – | – |
| `TELEGRAM_BOT_TOKEN` | – | – | – | – | ✅ | – |
| `TWILIO_ACCOUNT_SID` / `_AUTH_TOKEN` / `_WHATSAPP_FROM` (skip per §5) | – | – | – | – | (optional) | – |
| `INGESTION_GATEWAY_URL` | – | – | – | – | ✅ | ✅ |
| `IMAP_HOST` / `_PORT` / `_USER` / `_PASSWORD` | – | – | – | – | – | ✅ |

Get each external key here:
- **Azure Form Recognizer + Blob Storage**: portal.azure.com → create a "Document Intelligence" resource (Form Recognizer) and a "Storage account" (free trial gives $200 credit for 30 days; ongoing cost is pay-per-use as in §6).
- **OpenAI**: platform.openai.com/api-keys.
- **Telegram bot**: message **@BotFather** on Telegram → `/newbot` → get the token instantly, free.
- **IMAP app password**: if using Gmail, enable 2FA then create an "app password" at myaccount.google.com/apppasswords.

---

## 10. Verify Tier B end-to-end
1. Hit each service's `/health` endpoint (all 6 have one) via its Railway public/internal URL — confirms it booted.
2. Upload a CSV bank statement via the ingestion-gateway → confirms Mongo + Redis wiring.
3. Upload a receipt photo via the OCR queue → confirms Azure Form Recognizer + Blob Storage wiring.
4. Watch a transaction flow through to **auto-posted** in the main app's Intelligence page (AI Decision Ledger) → confirms `classifier-service → VOUSFIN_API_URL` wiring.
5. Message your Telegram bot → confirms `bot-adapter → ingestion-gateway` wiring.

---

## 11. Scaling beyond the pilot

None of this is needed at 20 users — only reach for it once real usage justifies it:

| Signal | Next step |
|---|---|
| Railway costs climbing past ~$100/month | Move Tier B to DigitalOcean Kubernetes (DOKS) or AWS ECS Fargate — same Docker images, just orchestrated |
| Atlas M2 feels slow / hits storage limits | M5 → M10 (M10 also unlocks real Atlas Vector Search for the main app's RAG, replacing the local-embedding fallback) |
| Need WhatsApp after all | Add Twilio back into `bot-adapter` — no code change, just the 3 env vars |
| Want experiment tracking / drift dashboards | Turn on Prometheus + Grafana (already in `docker-compose.yml`, just needs deploying alongside Tier B) |
| classifier-service retraining gets slow | It's still CPU-only (XGBoost) — a bigger Railway/DO instance is enough; no GPU is needed at any realistic VousFin scale |

---

## 12. Quick reference — everything in one table

| Layer | Platform | Pilot cost |
|---|---|---|
| Frontend | Vercel | $0 |
| Main backend + AI (DeepSeek) | Vercel + DeepSeek | ~$2–5/mo |
| Database | Atlas M2 | ~$9/mo |
| Tier B microservices + Redis + MLflow | Railway | ~$15–30/mo |
| OCR (Azure Form Recognizer + Blob) | Azure | ~$1–5/mo |
| OCR vision fallback | OpenAI | ~$1–3/mo |
| Email | Brevo | $0 |
| Cron | cron-job.org | $0 |
| Bot | Telegram | $0 |
| **Total** | | **≈ $30–55/month for 20 pilot testers** |
