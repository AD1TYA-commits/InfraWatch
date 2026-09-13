# User Guide

InfraWatch has two distinct experiences depending on your role. Sign in (or
register) at `/login` / `/register` — you're redirected to the right one
automatically.

## As an analyst

### Signing in

Use the seeded demo account (`analyst@infrawatch.local` /
`demo-analyst-2025`) or register your own analyst account. You land on the
main dashboard at `/`.

### The dashboard

- **KPI cards** — total registered works and counts by status
  (normal/watch/high/critical), computed over the *entire* registry via
  `GET /api/projects/kpi-summary`, not just the page currently loaded.
- **Geospatial map** — every project with a GPS coordinate, as a Leaflet
  marker; click one to see its status.
- **Project registry table** — S.No., Work ID (or `#id` if none), project
  name, sector, reported progress, and a verification-priority status
  badge. A project's coordinates are shown under its name when present, or
  "No GPS on record" (with "— manual evidence" if a contractor has already
  uploaded photos for it) when not.

### Filtering and paging

- **Search** — matches project name or sector.
- **Priority filter** — All / Least (Red) / Medium (Yellow) / Normal (Green).
- **Sector filter** — appears once projects are loaded, built from the
  sectors actually present on the current page.
- **Registry filter** — All Sources / MPLADS Registry (MoSPI) / Manual Field
  Evidence / Contractor / Other — maps to the `data_source` field
  (`india-mplads-works`, `manual-field-evidence`, `contractor-registered`).
- **Pagination** — the registry runs to 1,000+ real rows, so the table loads
  100 at a time (`GET /api/projects?page=&page_size=100`); use Previous/Next
  to move between pages. The KPI cards always reflect the full registry
  regardless of which page you're viewing.

### The project detail page

Click any project name (or its "Analyze →" action) to open
`/projects/{id}`. You'll see:

- **Overview cards** — reported progress, approved budget, T1 baseline date,
  T2 latest observation date.
- **Project scope** — the description on record.
- **Composite risk assessment** — the 0-100 score, its LOW/MEDIUM/HIGH/
  CRITICAL level, and all four contributing factors (satellite discrepancy,
  financial, timeline, duplicate-work) with each factor's own score, weight,
  and plain-language explanation. If similar nearby works were found, the
  count is shown — flagged for review, not confirmed as duplicates.
- **AI Satellite Screening tab** — before/after image slider (drag to
  compare T1 vs. T2), any AI-narrated change summary and detected change
  categories, and a recommendation banner (Field verification recommended /
  Review recommended / No significant discrepancy). "Run Analysis Again"
  re-runs the pipeline live. "Fetch Latest Sentinel-2" forces a fresh
  imagery pull (`POST /api/projects/{id}/ingest`). Projects with no GPS
  coordinate show a note that evidence came from manually-supplied photos
  instead of a satellite map location.
- **Milestones tab** and **Financials tab** — the schedule and disbursement
  records on file for the project, where present.
- **Export Report (PDF)** — generates a field-verification PDF client-side
  (via jsPDF; no backend round trip) from the current analysis, evidence,
  and project data — useful to hand to a field team.

### What to do with a flagged project

A HIGH or CRITICAL composite score, or a "Field verification recommended"
banner, means: schedule an on-site check. It does not mean fraud has been
established — read the factor explanations to understand *why* it was
flagged (a large satellite discrepancy is a very different situation from a
financial-overrun-only flag) before deciding what to check for on site.

## As a contractor

### Signing in

Use the seeded demo account (`contractor@infrawatch.local` /
`demo-contractor-2025`) or register with the "Contractor" role selected.
You land on `/contractor`, with three tabs.

### My Projects

Lists everything you've registered or uploaded evidence for
(`GET /api/projects/mine`), each tagged Satellite-screened / Manual evidence
/ Awaiting evidence. Click through to the same project detail page an
analyst sees.

### Register New Project

Creates a brand-new project (`POST /api/projects`). **Latitude and longitude
are mandatory** — every newly-registered project gets real satellite
screening automatically from the moment it's created; there is no way to
register a new project without a coordinate. If you don't have one yet for
an existing legacy record, use "Upload Evidence" instead. Fields: name,
sector, reported progress (%), latitude, longitude, description.

### Upload Evidence

For an **existing** project that has no GPS coordinate on record (a common
situation for older, already-registered works). Pick the project from a
dropdown (pre-filtered to `evidence_source=unavailable`), attach a before
photo and an after photo (e.g. Google Maps/Earth screenshots, or actual site
photos), and submit
(`POST /api/projects/{id}/evidence/upload`, multipart). This runs the exact
same real change-detection model used for satellite imagery — a real model
score, not a placeholder number — and immediately shows the observable
change percentage and region count detected. You can only upload evidence
for a project you own or that has no owner yet, and only if it genuinely has
no coordinate; the API rejects an upload attempt against a project that
already has one (it's already satellite-screened automatically).

## Frequently asked questions

**Why does a project show "No GPS on record"?**
Most bulk-imported real MPLADS records don't publish a GPS coordinate — this
is a property of the source data, not something InfraWatch failed to
collect. Such a project can't be satellite-screened until either a
coordinate becomes available or a contractor uploads manual evidence for it.

**Is the risk score proof of anything?**
No. It's a screening prioritization signal for human review — see the
disclaimer on every risk response and
[01-project-overview.md](01-project-overview.md).

**Can an analyst upload evidence or register a project?**
No — those actions are contractor-only, enforced on the backend
(`require_role("contractor")`) as well as hidden from the analyst UI.

**Can a contractor see the full registry / map dashboard?**
No — `/` is analyst-only; a contractor who navigates there is redirected
back to `/contractor`.
