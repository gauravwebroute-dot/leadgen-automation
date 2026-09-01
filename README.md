# Lead Generation Automation

Finds target companies by industry/city, finds decision-maker contacts
(facilities, maintenance, plant, purchasing, procurement titles), verifies
contact emails, and syncs approved leads into Odoo CRM. Includes a demo
dashboard for reviewing leads before they're approved.

Every stage tested end-to-end (routes, DB writes, dedup, background
pipeline, error handling, dashboard serving) before packaging.

## Pipeline

1. **Company finder** -- searches Google Places API for real businesses
   matching `{industry}` near `{city}`. Returns structured data (name,
   address, phone, website) -- not parsed search snippets.
2. **Contact finder** -- for each company + target title, searches
   `site:linkedin.com/in "{title}" "{company}"` via Google Custom Search
   and extracts candidate names.
3. **Enrichment** -- guesses `first.last@domain` from the company website,
   then verifies it through Hunter's Email Verifier API (MX + SMTP check).
   Only marked `verified` if Hunter confirms the mailbox is real; otherwise
   tagged `risky`, `invalid`, or `unverified_guess` so nothing masquerades
   as trustworthy data.
4. **Human review** -- every lead lands as `pending`. Use the dashboard
   (or `POST /leads/{id}/approve`) to review before anything reaches Odoo.
5. **Odoo sync** -- `POST /leads/sync-approved` pushes all approved leads
   as `crm.lead` records.

## Setup

```bash
cp .env.example .env          # fill in the keys below
pip install -r requirements.txt
docker compose up -d          # starts local Postgres
uvicorn app.main:app --reload
```

Open `http://localhost:8000/dashboard/` for the review UI, or
`http://localhost:8000/docs` for the raw API.

### Getting your keys

**Google Places API** (company discovery)
1. console.cloud.google.com -> APIs & Services -> Library -> enable
   "Places API (New)".
2. Create an API key under Credentials.
3. `GOOGLE_PLACES_API_KEY` in `.env`.

**Google Custom Search** (contact discovery on LinkedIn only)
1. programmablesearchengine.google.com -> create a search engine.
2. Under "Sites to search", add `linkedin.com`. ("Search the entire web"
   is no longer available for new engines as of Jan 2026 -- Google now
   caps free/new engines at 50 specific domains -- so this is scoped to
   just LinkedIn, which is all the contact finder needs.)
3. Copy the Search engine ID as `GOOGLE_CSE_CX`.
4. Enable the Custom Search API in Cloud Console, generate an API key as
   `GOOGLE_CSE_API_KEY`.

**Hunter.io** (email verification)
1. hunter.io -> sign up (free tier: 50 credits/month, ~100 verifications).
2. Copy your API key as `HUNTER_API_KEY`.

**Odoo**
1. Odoo Settings -> Users -> your user -> API Keys -> generate one.
2. `ODOO_URL` (e.g. `https://yourcompany.odoo.com`), `ODOO_DB`,
   `ODOO_USERNAME`, `ODOO_API_KEY` in `.env`.

## Usage

Via the dashboard (`/dashboard/`): click "Start new search", fill in city
+ industries, review leads under each tab, approve/reject, then "Sync
approved to Odoo".

Via curl:
```bash
curl -X POST localhost:8000/search-runs/ \
  -H "Content-Type: application/json" \
  -d '{"city": "Anaheim", "industries": ["manufacturing", "metal fabrication"]}'

curl "localhost:8000/leads/?status=pending"
curl -X POST localhost:8000/leads/3/approve
curl -X POST localhost:8000/leads/sync-approved
```

## Known limitations (by design, for v1)

- **Google Places API is billed per request** (not free like the old CSE
  "entire web" option was) -- check current pricing before running large
  batches.
- **Google CSE free tier = 100 queries/day**, and contact discovery is
  scoped to LinkedIn only per the Jan 2026 domain cap.
- **Hunter free tier = ~100 verifications/month** -- budget your search
  batch sizes accordingly, or the enrichment stage falls back to
  `unverified_guess` once credits run out.
- **Name extraction from LinkedIn search snippets is still heuristic**
  (regex on "First Last - Title - Company" patterns) -- this is the one
  piece not yet backed by a structured API. A people-data API (Apollo.io,
  ContactOut) would remove this; not wired up in v1.
- **No Alembic migrations yet** -- tables are created via
  `Base.metadata.create_all()` on startup. Fine for one dev DB; add
  Alembic before this touches a shared/production database.

## What to build next (not included)

- Swap `site:linkedin.com/in` contact search for a structured people-data
  API (Apollo.io/ContactOut) to remove the last heuristic-parsing step.
- Rate-limit backoff / query budget tracking against the free-tier caps.
- Auth on the dashboard before it's exposed anywhere but localhost.
