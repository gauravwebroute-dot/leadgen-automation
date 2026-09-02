# Lead Generation Automation

Finds target companies by industry/city, finds decision-maker contacts
(facilities, maintenance, plant, purchasing, procurement titles) with
verified emails, and syncs approved leads into Odoo CRM. Includes a demo
dashboard for reviewing leads before they're approved.

## Pipeline

1. **Company finder** -- searches Google Places, Outscraper, or SerpApi
   (configurable) for real businesses matching `{industry}` near `{city}`.
   Returns structured data: name, address, phone, website.
2. **Contact finder** -- for each company, looks up its website domain in
   **Hunter's Domain Search API**, which returns real people at that
   domain: name, job title, department, and an email with Hunter's own
   verification status attached. Contacts are kept if their title matches
   your target list (word-overlap match, so "Plant Manager" also matches
   "Plant Operations Manager"). One Hunter credit per company -- no
   per-title multiplier, no LinkedIn search, no name-guessing regex, no
   email-pattern-guessing. Everything here is real data Hunter found, not
   inferred.
3. **Human review** -- every lead lands as `pending`. Use the dashboard
   (or `POST /leads/{id}/approve`) to review before anything reaches Odoo.
4. **Odoo sync** -- `POST /leads/sync-approved` pushes all approved leads
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

**Company discovery** -- pick ONE via `COMPANY_DISCOVERY_PROVIDER`:
- `outscraper` -- outscraper.com, free monthly credits for testing
- `serpapi` -- serpapi.com, free tier: 100 searches/month
- `places` -- Google Cloud Console, enable "Places API (New)", billed per
  request (no free tier)

**Hunter.io** (contact discovery + email verification)
1. hunter.io -> sign up (free tier: 50 credits/month).
2. Copy your API key as `HUNTER_API_KEY`.
3. Make sure the companies you search have a real `website` populated by
   the company finder -- Hunter needs a domain, not just a company name.

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

- **Hunter free tier is 50 credits/month.** The `max_companies_for_contacts`
  cap (default 5) protects this -- each run uses at most that many credits.
- **Small/obscure companies may have no Hunter data at all** -- Hunter's
  coverage depends on public web presence. If a run's warning says "found
  the domain but no one matched your target titles," it may mean Hunter
  has zero people on file for that company, not that your titles are wrong.
- **Company discovery providers each cost differently** -- Outscraper and
  SerpApi have free tiers for testing; Google Places is billed per
  request with no free tier. Check current pricing before large batches.
- **No Alembic migrations yet** -- a lightweight auto-migration in
  `app/db.py` adds missing columns to existing tables on startup (fine
  for a solo project against Render's Postgres); switch to real Alembic
  migrations before more than one person touches this schema.

## What to build next (not included)

- If Hunter's coverage is too thin for smaller companies, a paid
  people-data API (Apollo.io, ContactOut) could supplement it.
- Rate-limit backoff / query budget tracking against the free-tier caps.
- Auth on the dashboard before it's exposed anywhere but localhost.
