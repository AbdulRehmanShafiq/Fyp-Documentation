# VousFin — Deployment Guide (Free/Cheap, Fine Performance)

Practical, step-by-step guide to running VousFin's confirmed live stack (frontend + backend + database + jobs + email + AI) for as close to $0/month as possible, with a clear upgrade path if you outgrow the free tiers. Numbers/prices are best-known as of this writing — **always confirm current prices on each provider's pricing page before committing**, since they change.

> **Scope note:** this guide covers the main app (`vousfin-backend-main` Express API, `vousfin-frontend-main` React SPA, MongoDB, cron jobs, email, DeepSeek AI). It does **not** cover the separate `ingestion-gateway` / `ocr` / `classifier-service` / `reconciliation` microservices referenced by the frontend's `VITE_INGESTION_URL` / `VITE_OCR_URL` / `VITE_CLASSIFIER_URL` / `VITE_RECONCILIATION_URL` (ports 8001–8004) — I could not confirm whether those are currently deployed anywhere. If the **AI Review Queue** or **Reconciliation Exceptions** pages don't load data for you in production, that's why; ask me to investigate and either wire them into the main backend or deploy them separately.

---

## 1. The DeepSeek API key — where it goes

1. Get a key at **https://platform.deepseek.com/api_keys** (sign up → API Keys → Create new key).
2. Add funds on the **Billing** page (a $2 top-up is accepted; see §2 for how far it goes).
3. Put the key in **`vousfin-backend-main/.env`** (create the file from `.env.example` if it doesn't exist):
   ```
   DEEPSEEK_API_KEY=sk-your-real-key-here
   DEEPSEEK_MODEL=deepseek-chat
   ```
4. For the **production deployment** (Vercel), add the same variable in the backend project's **Settings → Environment Variables**:
   - Name: `DEEPSEEK_API_KEY`, Value: your key, Environment: Production (and Preview if you use preview deploys).
   - Redeploy (or it picks it up on the next deploy) for it to take effect.
5. That's the **only** AI credential the app needs now — `GEMINI_API_KEY` and `GROQ_API_KEY` are no longer read anywhere and can be deleted from your env if present.

---

## 2. How far will $2 of DeepSeek credit go?

DeepSeek's `deepseek-chat` pricing (verify current numbers at **platform.deepseek.com → API Pricing** — they periodically run off-peak discounts too):

| | Price per 1M tokens |
|---|---|
| Input | ≈ $0.27 |
| Output | ≈ $1.10 |

VousFin's AI calls, by feature:

| Feature | Typical input tokens | Typical output tokens | Cost/call |
|---|---|---|---|
| Natural-language transaction parse | ~2,000 (system prompt + your Chart of Accounts) | ~300 | **≈ $0.0009** |
| AI Assistant chat (RAG-grounded) | ~3,700 (question + retrieved context) | ~400 | **≈ $0.0014** |
| How-to search | ~800 | ~200 | **≈ $0.0004** |

**$2 of credit ≈ 1,400–2,200 AI calls**, depending on the mix. In practice:

| Usage pattern | Calls/day | $2 lasts about |
|---|---|---|
| Light (personal use, a handful of transactions + a few questions) | ~10–20 | **3–4 months** |
| Moderate (small business, daily bookkeeping + regular assistant use) | ~40–60 | **~1 month** |
| Heavy (active testing/demoing all day) | ~100+ | **~2–3 weeks** |

You will not be caught off guard: the app's requests fail with a clear "AI service is temporarily unavailable" message if the balance runs out — nothing breaks silently, and no accounting data is affected (the ledger never depends on AI availability).

---

## 3. Recommended platforms — $0/month baseline

This is the exact stack VousFin already runs on in production today (per project history), matched to the actual code (Vercel serverless function config, cron-trigger routes, SMTP config, optional Redis).

| # | Service | What it's for | Platform | Cost | Card required? |
|---|---|---|---|---|---|
| 1 | Backend hosting | The Express API (`vousfin-backend-main`) | **Vercel** (Hobby plan) | $0 | No |
| 2 | Frontend hosting | The React SPA (`vousfin-frontend-main`) | **Vercel** (Hobby plan) | $0 | No |
| 3 | Database | MongoDB | **MongoDB Atlas** (M0 free tier, 512MB shared) | $0 | No |
| 4 | Scheduled jobs | Payment reminders, tax snapshots, forecast retrain, etc. — the app has no always-on process to run these itself on serverless | **cron-job.org** | $0 | No |
| 5 | Transactional email | Password reset, invites, reminders | **Brevo** (free SMTP relay, 300 emails/day) | $0 | No |
| 6 | AI (LLM) | NL parsing, AI assistant, how-to search | **DeepSeek API** | pay-as-you-go, ~$2–5/month at light-to-moderate use | Yes (for top-up) |
| 7 | Redis (optional) | Background job queue, report cache — the app runs fine without it (built-in synchronous fallback) | **Upstash Redis** (free tier, 10K commands/day) | $0 | No |
| 8 | Custom domain (optional) | Nicer URL than `*.vercel.app` | Namecheap / Porkbun | ~$10–15/**year** | Yes |

**Total to run everything at fine speed: $0/month fixed cost + a few dollars/month of DeepSeek usage.** Items 7 and 8 are genuinely optional — skip them and the app works fully without them.

---

## 4. Step-by-step setup

### Step 1 — MongoDB Atlas (database)
1. Create a free account at **mongodb.com/cloud/atlas**.
2. Create a new project → build a database → choose **M0 Free**.
3. Create a database user (username/password) — save the password somewhere safe, you'll need it once.
4. Network Access → **Allow access from anywhere** (`0.0.0.0/0`) — required because Vercel's serverless functions run from rotating IPs.
5. Get the connection string (Connect → Drivers → Node.js) — looks like `mongodb+srv://user:pass@cluster.mongodb.net/vousfin`.
6. This becomes your `MONGO_URI`.

### Step 2 — Brevo (email)
1. Sign up free at **brevo.com**.
2. SMTP & API → SMTP → copy your SMTP credentials (host is `smtp-relay.brevo.com`, port `587`).
3. These become `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_SECURE=false`, `SMTP_USER`, `SMTP_PASS` in your env.

### Step 3 — DeepSeek (AI)
Already covered in §1. You just need `DEEPSEEK_API_KEY`.

### Step 4 — Deploy the backend to Vercel
1. Push `vousfin-backend-main` to its own GitHub repo (already done).
2. On **vercel.com** → New Project → import the backend repo.
3. Framework preset: **Other** (it's a plain Node/Express app served via `api/index.js`, already configured in `vercel.json`).
4. Add every variable from `.env.example` under **Settings → Environment Variables** (at minimum: `MONGO_URI`, `JWT_SECRET`, `CLIENT_URL`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `SMTP_*`, `CRON_SECRET` — pick your own random string for `CRON_SECRET`).
5. Deploy. Note the resulting URL (e.g., `https://vousfin-backend.vercel.app`).
6. Visit `https://your-backend-url/health` — you should see a healthy JSON response.

### Step 5 — Deploy the frontend to Vercel
1. Push `vousfin-frontend-main` to its own GitHub repo (already done).
2. New Project → import the frontend repo. Framework preset: **Vite**.
3. Add `VITE_API_BASE_URL=https://your-backend-url/api/v1` as an environment variable.
4. Deploy. Note the resulting URL (e.g., `https://vousfin.vercel.app`).
5. Go back to the **backend's** env vars and set `CLIENT_URL` to this frontend URL (needed for CORS + email links), then redeploy the backend.

### Step 6 — cron-job.org (scheduled jobs)
Serverless functions don't stay running, so the app's `node-cron` schedules never fire in production — instead, an external free scheduler calls the same job logic on demand via `POST /api/v1/jobs/run/<job-name>`.

1. Sign up free at **cron-job.org**.
2. For each job below, create a cron job:
   - URL: `https://your-backend-url/api/v1/jobs/run/<job-name>`
   - Method: `POST`
   - Header: `x-cron-secret: <the CRON_SECRET you set in Step 4>`
3. Suggested schedule (adjust to taste):

   | Job name | Suggested cadence |
   |---|---|
   | `payment-reminders` | Daily, 9am |
   | `fx-rate-sync` | Daily, 6am |
   | `scheduled-reports` | Daily, 7am |
   | `tax-snapshots` | Daily, midnight |
   | `tax-return-autoprepare` | Daily, 1am |
   | `anomaly-scan` | Daily, 2am |
   | `forecast-accuracy` | Weekly |
   | `forecast-materialize` | Daily |
   | `forecast-retrain` | Weekly |
   | `compliance-reminders` | Daily, 8am |
   | `fixed-asset-depreciation` | Daily, 4am |
   | `thirteen-week-cash` | Daily |

### Step 7 — verify end to end
1. Sign up for a business in the deployed frontend.
2. Add a transaction via the natural-language box — confirms `DEEPSEEK_API_KEY` works.
3. Check your email for the verification link — confirms Brevo works.
4. Trigger one cron job manually (`curl -X POST -H "x-cron-secret: ..." https://your-backend-url/api/v1/jobs/run/fx-rate-sync`) — confirms the cron wiring works.

---

## 5. If you outgrow the free tier

None of this is needed to start — only reach for it when you actually feel a limit (real paying users, large data, or Vercel's commercial-use terms apply):

| Limit you'll hit | Upgrade | Cost |
|---|---|---|
| Atlas M0's 512MB storage / shared, throttled performance | Atlas **M2** (2GB) or **M5** (5GB), still shared | ~$9–25/month |
| Want real **Atlas Vector Search** instead of the app's built-in local-embedding fallback (fine for small datasets, slower at scale) | Atlas **M10** dedicated cluster (cheapest tier that supports Vector Search) | ~$57/month |
| Vercel Hobby is for personal/non-commercial projects — if VousFin becomes a paying product, you need a compliant plan | **Vercel Pro** | $20/month/member |
| Brevo's 300 emails/day | Brevo **Starter** | ~$9/month |
| Want background job processing (BullMQ) instead of the built-in synchronous fallback, for faster receipt/email intake | Upstash Redis paid tier, or a small **Railway/Render** worker | ~$5–10/month |

**Bottom line:** stay on row 1 of §3 as long as you can — it costs nothing but DeepSeek usage, and DeepSeek itself is inexpensive enough that a solo/small-business user will spend single-digit dollars a month.
