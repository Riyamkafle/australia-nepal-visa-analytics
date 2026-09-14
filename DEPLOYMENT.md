# Deployment Documentation — AusNepal Visa Analytics

This document describes the production architecture, deployment process, and configuration for the AusNepal Visa Analytics platform: a full-stack business intelligence dashboard analyzing Australian student visa outcomes for Nepali applicants, built on official Department of Home Affairs data.

**Live URLs**
- Frontend: https://aus-visa-insight.reyamkafle.workers.dev
- Backend API: https://australia-nepal-visa-analytics.onrender.com

**Repositories**
- Frontend: [github.com/Riyamkafle/aus-visa-insight](https://github.com/Riyamkafle/aus-visa-insight)
- Backend: [github.com/Riyamkafle/australia-nepal-visa-analytics](https://github.com/Riyamkafle/australia-nepal-visa-analytics)

---

## 1. Architecture Overview

The platform is split into two independently deployed services that communicate exclusively over HTTPS via a REST API. There is no shared runtime, shared filesystem, or shared deployment pipeline between them — each can be redeployed, scaled, or replaced without touching the other.

```
┌─────────────────────────┐         HTTPS / JSON          ┌──────────────────────────┐
│      Frontend            │ ─────────────────────────────▶│       Backend API        │
│  React + TypeScript      │                                │  Django + DRF            │
│  TanStack Start (SSR)    │◀───────────────────────────────│                           │
│  Cloudflare Workers       │                                │  Render (Web Service)    │
└─────────────────────────┘                                └────────────┬─────────────┘
                                                                          │
                                                                          │ psycopg2
                                                                          ▼
                                                              ┌──────────────────────────┐
                                                              │      PostgreSQL           │
                                                              │      Neon (managed)       │
                                                              └──────────────────────────┘
```

| Layer | Technology | Hosting | Cost |
|---|---|---|---|
| Frontend | React 19, TypeScript, Vite, TanStack Start/Router, Tailwind, Recharts | Cloudflare Workers (Nitro SSR build) | Free |
| Backend | Django 5, Django REST Framework | Render Web Service | Free |
| Database | PostgreSQL | Neon (managed, serverless) | Free |

All three tiers run on free tiers, suitable for a portfolio-scale deployment. Known limitation: Render's free web service spins down after ~15 minutes of inactivity, adding a 30–50 second cold-start delay to the first request after idle. Neon auto-resumes on query without manual intervention.

---

## 2. Backend Deployment (Render + Neon)

### 2.1 Database provisioning

The production database was **not** built from scratch on the hosting provider. The existing, locally validated PostgreSQL database (22 MB, containing verified visa data across `nepal_merged`, `fy_summary`, `monthly_trend`, and related tables) was migrated directly:

```bash
# 1. Dump the local, validated database
pg_dump -h localhost -U postgres -d student_visa_db -F c -f visa_analytics_backup.dump

# 2. Restore into Neon (using the non-pooled/direct connection string)
PGPASSWORD='<password>' PGSSLMODE=require pg_restore \
  -h <neon-host> -U neondb_owner -d neondb \
  --no-owner --no-privileges -v visa_analytics_backup.dump
```

This approach was chosen over re-running the data pipeline (`import_homeaffairs.py` → `rebuild_data_sources.py` → `load_csv_data.py`) on the server because several of the pipeline's upstream extraction scripts (`extract_nepal_*.py`) had already been removed from the repository after their output was finalized. A fresh pipeline run on a clean server would have had no way to regenerate the source CSVs. Restoring a verified dump guarantees the production database is byte-for-byte the same data that was validated locally.

**Post-restore verification:** row counts for key tables (`nepal_merged`, `fy_summary`, `monthly_trend`) were compared between local and Neon and confirmed identical before proceeding.

Neon connection detail: the dashboard provides two connection strings — a **pooled** (PgBouncer, hostname suffixed `-pooler`) string for normal application traffic, and a **direct** string for schema-level operations. `pg_restore` requires the direct connection; the pooled connection is used for `DB_HOST` in the running application's environment variables.

### 2.2 Dependency management

`requirements.txt` was **not** generated via a blind `pip freeze`. Runtime dependencies were determined by grepping actual import statements across the modules Django loads at startup (`analytics/views.py`, `analytics/serializers.py`, `analytics/models.py`, `upload/views.py`, `upload/serializers.py`, `upload/models.py`, and their transitive imports):

```bash
grep -rn "^import\|^from" analytics/*.py upload/*.py | grep -E "pandas|numpy|sqlalchemy|openpyxl|requests"
```

This surfaced a real bug: `upload/utils.py` imports `pandas`, and `upload/views.py` imports from `upload/utils.py`. Because `analytics/urls.py` imports `upload.views` at module load time, `pandas` is a **hard runtime dependency of the whole Django app**, not just an offline data-processing convenience — omitting it crashes every request with a 500 error, not just CSV/Excel upload endpoints specifically. `openpyxl` was retained for the same reason (pandas' Excel engine).

Final production `requirements.txt`:
```
django>=5.0,<6.0
djangorestframework>=3.15
django-cors-headers>=4.3
psycopg2-binary>=2.9
python-decouple>=3.8
gunicorn>=21.2
whitenoise>=6.6
pandas>=2.2
openpyxl>=3.1
```

`sqlalchemy` and `requests` were deliberately excluded from the web service's dependency list — they are used only by the offline data-refresh pipeline scripts, which are not executed by the running web service.

### 2.3 Render Web Service configuration

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Region | Singapore |
| Build command | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| Start command | `gunicorn core.wsgi:application` |
| Instance type | Free |

**Environment variables** (set via Render dashboard, never committed to the repository):

| Variable | Purpose |
|---|---|
| `DEBUG` | `False` in production |
| `SECRET_KEY` | Freshly generated for production, distinct from local dev key |
| `ALLOWED_HOSTS` | `australia-nepal-visa-analytics.onrender.com` |
| `DB_NAME`, `DB_USER`, `DB_HOST`, `DB_PORT`, `DB_PASSWORD` | Neon connection details (individual variables, matching the existing `python-decouple`-based `settings.py`, rather than a single `DATABASE_URL` — no code change required) |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of permitted frontend origins (see §4) |

Static files are served via WhiteNoise (`CompressedManifestStaticFilesStorage`), already correctly configured in `settings.py` prior to deployment — no changes needed.

---

## 3. Frontend Deployment (Cloudflare Workers)

### 3.1 Why Cloudflare Workers, not a generic static host

Inspecting the build output before choosing a host revealed the frontend is not a plain client-side SPA. It is built with **TanStack Start**, which produces a server-side rendering (SSR) bundle via Nitro:

```bash
npm run build
# ...
◐ Building [Nitro] (preset: cloudflare-module, compatibility: 2026-09-13)
✔ Generated .output/public
✔ Generated .output/server/wrangler.json
```

The build produces three artifacts:
- `.output/public/` — static assets
- `.output/server/` — an SSR server bundle (`index.mjs`) targeting the Cloudflare Workers runtime specifically (the `fetch(request, env, ctx)` handler signature in `src/server.ts` is Workers-specific, not a generic Node server)
- `.output/server/wrangler.json` — a Workers deployment manifest with a static-assets binding, `nodejs_compat` enabled, no additional bindings (no KV/D1/R2)

A plain static host (e.g. a bare "static site" product) would only serve `.output/public` and silently drop the SSR server — breaking any server-rendered behavior. Cloudflare Workers is the platform this build is already configured to target, so it was chosen to avoid overriding the Nitro preset or modifying `vite.config.ts`.

### 3.2 Cloudflare configuration

Deployed via Cloudflare's unified Workers & Pages Git integration:

| Setting | Value |
|---|---|
| Repository | `Riyamkafle/aus-visa-insight`, branch `main` |
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy` |
| Environment variable | `VITE_API_BASE_URL` = `https://australia-nepal-visa-analytics.onrender.com` |

**Deploy command note:** an initial attempt explicitly set the deploy command to `npx wrangler deploy --cwd .output/server`, reasoning that wrangler would need to be told where the Nitro-generated config lived. This caused a deploy failure:

```
✘ [ERROR] Found both a user configuration file at "wrangler.json"
  and a deploy configuration file at "../../.wrangler/deploy/config.json".
  But these do not share the same base path so it is not clear which should be used.
```

Cloudflare's build pipeline auto-generates its own deploy configuration (`.wrangler/deploy/config.json`) matched to the project structure; the manual `--cwd` override caused wrangler to see two conflicting configs. Reverting to the plain `npx wrangler deploy` resolved it — Cloudflare's own tooling correctly auto-detects and redirects to `.output/server/wrangler.json` without manual intervention:

```
Using redirected Wrangler configuration.
 - Configuration being used: ".output/server/wrangler.json"
 - Deploy configuration file: ".wrangler/deploy/config.json"
```

**Lesson:** when a build tool (Nitro, in this case) already generates provider-specific deployment configuration, prefer the provider's default command over manually specifying paths — the auto-detection is usually already aware of the generated config location.

---

## 4. Cross-Origin Configuration (CORS)

The frontend and backend are on different origins (`*.workers.dev` and `*.onrender.com`), so the backend must explicitly allow the frontend's origin via `django-cors-headers`.

Initial deployment used a `CORS_ALLOWED_ORIGINS` value scoped to local development only:
```
http://localhost:5173,http://localhost:8080
```

After the frontend went live, all API requests failed with:
```
Access to fetch at '.../api/overview/' from origin 'https://aus-visa-insight.reyamkafle.workers.dev'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
```

Fixed by updating the Render environment variable to include the production frontend origin:
```
http://localhost:5173,http://localhost:8080,https://aus-visa-insight.reyamkafle.workers.dev
```

Render automatically redeploys on environment variable changes, applying the new CORS policy without any code changes.

---

## 5. Secrets Handling

- No `.env` files are committed to either repository (`.gitignore` in both repos excludes `.env`, `.env.local`, `.env.*.local`).
- `SECRET_KEY` (Django) is generated fresh for production via `python -c "import secrets; print(secrets.token_urlsafe(50))"` and entered directly into Render's environment variable UI — never reused from the local development key.
- Database credentials are entered directly into Render's environment variable UI, sourced from Neon's dashboard.
- Where a secret was accidentally exposed in a non-production context during setup (e.g. pasted in plaintext during troubleshooting), it was rotated immediately rather than left in place — applies to both the Neon database password and the Django `SECRET_KEY`.

---

## 6. Known Limitations

- **Cold starts (backend):** Render's free tier spins the web service down after ~15 minutes of inactivity. The first request after idle takes 30–50 seconds while the instance restarts. Neon's database does not have this issue — it auto-resumes on query.
- **No automated data refresh:** the three-stage data pipeline (`import_homeaffairs.py` → `rebuild_data_sources.py` → `load_csv_data.py`) exists in the backend repository but is not scheduled. Refreshing production data currently requires running the pipeline manually against the production database, or repeating the dump/restore process from an updated local database.
- **Free-tier constraints:** Neon's free tier caps storage at 0.5 GB (current usage: ~22 MB) and monthly compute at 100 CU-hours — ample headroom for a portfolio-scale deployment, but worth monitoring if traffic or data volume grows significantly.

---

## 7. Deployment Checklist (for future redeploys)

**Backend (Render)**
1. Push changes to `main` on `australia-nepal-visa-analytics` — Render auto-deploys.
2. If dependencies changed, verify `requirements.txt` reflects actual runtime imports (see §2.2 methodology) before pushing.
3. Check the Render deploy log for `Build successful` and confirm no `ModuleNotFoundError` on startup.

**Frontend (Cloudflare Workers)**
1. Push changes to `main` on `aus-visa-insight` — Cloudflare auto-deploys via the Git integration.
2. Confirm the build log shows `Configuration being used: ".output/server/wrangler.json"` and ends with a `Deployed` line and the live `workers.dev` URL.

**After any backend URL or frontend URL change**
1. Update `VITE_API_BASE_URL` in Cloudflare's environment variables if the backend URL changes.
2. Update `CORS_ALLOWED_ORIGINS` in Render's environment variables if the frontend URL changes.
