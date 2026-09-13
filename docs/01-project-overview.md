# Project Overview — What InfraWatch Actually Is

## 1. The problem, in plain terms

MPLADS (Members of Parliament Local Area Development Scheme) funds tens of
thousands of small local infrastructure works across India — roads, health
sub-centres, water tanks, school extensions, and similar. Progress is
self-reported by whoever is implementing the work. Reviewers have no
independent, scalable way to sanity-check thousands of these self-reports
against what's actually happening on the ground.

InfraWatch is a screening layer for that gap: for each registered project,
it compares the *reported* progress percentage against *observable* change
between two images of the site (a real satellite pass, or manually-supplied
before/after photos), and surfaces the size of that gap as a prioritization
signal.

**This is explicitly not a fraud-detection system.** It does not determine
guilt, issue findings, or replace field inspection. A HIGH or CRITICAL flag
means "a human should look at this sooner rather than later" — nothing more.
Every risk-score API response carries this disclaimer verbatim
(`app/risk_engine.py`'s `PROTOTYPE_DISCLAIMER`):

> InfraWatch prototype risk score. These are automated screening indicators
> to help prioritize human review — they do NOT constitute proof of
> statutory violation, fraud, or contractor default. Field inspection is
> recommended for HIGH or CRITICAL tiers.

## 2. The idea: let evidence do the first pass

Reviewing every project by hand doesn't scale; ignoring the self-reports
entirely isn't reasonable either. InfraWatch's approach: run every project
through a deterministic, explainable screening pass, and let reviewers spend
their limited attention on whatever comes out flagged — instead of reading
every row of a thousand-project spreadsheet with no prioritization at all.

Two independent things feed that screening pass:

1. **Observable change vs. reported progress** — the core signal, worth 50%
   of the composite risk score. A project that reports 90% complete but
   shows almost no observable change between two images is worth a closer
   look; a project whose observable change roughly tracks its reported
   progress is not.
2. **Structured-data anomalies** — financial overrun (sanctioned vs. actual
   expenditure), timeline slippage/stalling, and similarity to other nearby
   works (possible duplicate billing) — together the other 50%.

## 3. How it actually works, end to end

For a project with a GPS coordinate:

1. The backend calls the standalone **satellite-service** microservice's
   `/pipeline/run` endpoint, which fetches real Sentinel-2 10m band imagery
   around that coordinate via a public STAC catalog, runs a pretrained
   ResNet18 feature-diff change-detection model ("PlanAura"), and narrates
   the result with Gemini (or a template fallback if no `GEMINI_API_KEY` is
   set).
2. InfraWatch stores the before/after scene references and the observed
   change percentage, compares it against the project's reported progress,
   and records a severity anomaly.
3. `GET /api/projects/{id}/risk` combines that satellite-discrepancy signal
   with the financial/timeline/duplicate-work signals into one 0-100
   composite risk score (`app/risk_engine.py`).

For a project with **no** GPS coordinate (most bulk-imported real
government records don't have one — see below), the same pipeline runs on
manually-photographed before/after evidence instead, once a contractor
uploads it: the exact same PlanAura model, called via satellite-service's
`/model/detect-images` endpoint, not a different or approximate one.

## 4. The three codebases

- **`backend/`** (this repo) — FastAPI: auth, the project registry,
  orchestration of whichever evidence pipeline applies, and the risk engine.
- **`frontend/`** (this repo) — Next.js dashboard: analyst registry/map/
  detail views, contractor portal.
- **`satellite-service/`** (sibling repo, `../satellite-service`) —
  standalone microservice, no shared code or database with InfraWatch. It
  is called over plain HTTP, the same way InfraWatch calls the Gemini API.
  Kept separate deliberately so it can be redeployed or restarted
  independently of the main backend's release.

## 5. What's real vs. what's synthetic

| Data | Real or synthetic | Notes |
|---|---|---|
| MPLADS works CSV (~1,000 rows, on disk) | Real | Government MPLADS/MoSPI-sourced records (`backend/data/processed/mplads_normalized.csv`) — a sanction/works registry, not a live construction tracker. Only 3 of the 1,000 rows carry a government-verified GPS coordinate and a real progress figure at all; the other 997 are kept as reference data on disk, not imported as registry projects (see below) |
| 4 legacy projects' before/after photos | Real | 3 (Goa: joggers park, crematorium; Nagaland: forest colony pond) are exactly the 3 MPLADS CSV rows with a real coordinate — used for map placement, but scored via the manually-supplied high-resolution photos rather than a 10m Sentinel-2 pass since that's what actually shows the change clearly for such small-scale works; 1 (Tamil Nadu, Udayarpalayam) is a standalone real example with no coordinate at all, not present in the CSV |
| PMGSY facility-location sample (24 rows) | Real locations, synthetic progress | Real facility coordinates; `reported_progress` is a synthetic placeholder since these are existing facilities, not in-progress works with a genuine self-report |
| Sentinel-2 imagery | Real | Actual 10m-band Sentinel-2 scenes fetched live via satellite-service for every coordinate-based project — no offline/bundled-image fallback |
| PlanAura change-detection model | Real | Pretrained ResNet18 feature-diff model, deterministic (same inputs → same output), not a placeholder heuristic |
| Risk engine scoring | Real, deterministic | No machine learning and no per-project hardcoding — see `app/risk_engine.py` and `docs/MERGE-NOTES.md` |

There is no synthetic/fabricated project data anywhere in the registry —
an earlier iteration had 6 fully-invented `[DEMO]` projects (fake
coordinates, a flat pasted-on shape composited onto a real satellite tile to
simulate "construction"); these were removed once real data covered the
"something to show immediately" need. See `docs/MERGE-NOTES.md`.

## 6. Roles

Two roles, enforced on both the API (`require_role` dependency) and the
frontend (`useRequireAuth` hook):

- **analyst** — read access to the full registry and risk data, runs
  analysis, exports PDF reports. Cannot register projects or upload
  evidence.
- **contractor** — registers new projects (GPS mandatory) and uploads
  before/after evidence for existing no-coordinate projects. Does not see
  the full analyst registry/map dashboard.

Full detail: [06-auth-and-roles.md](06-auth-and-roles.md).

## 7. Current status (be honest about this in a demo)

- Full-stack auth, deterministic risk scoring, and the manual-evidence
  workflow are implemented and tested (23 backend tests).
- The risk engine's weights (`app/config.py`'s `RISK_WEIGHTS`) and the
  LOW/MEDIUM/HIGH/CRITICAL score thresholds (`app/risk_engine.py`'s
  `_classify()`) are reasoned defaults, not calibrated against a labeled
  ground-truth dataset of confirmed cases.
- Production hardening beyond JWT + bcrypt + role gating (rate limiting,
  refresh tokens, password reset, audit-log UI) is not yet built.
- satellite-service has no auth of its own by design — it's meant to sit
  behind InfraWatch's backend on an internal network, not be exposed
  directly.

## Glossary

- **MPLADS** — Members of Parliament Local Area Development Scheme.
- **PMGSY** — Pradhan Mantri Gram Sadak Yojana (rural roads program); used
  here only as a source of real facility locations for a sample dataset.
- **AOI** — area of interest (the imagery window fetched around a project's
  coordinate).
- **STAC** — SpatioTemporal Asset Catalog, the API standard used to search
  for Sentinel-2 scenes.
- **Composite risk score** — the 0-100 weighted combination of the four risk
  factors; see [05-architecture-and-api-reference.md](05-architecture-and-api-reference.md).
- **Evidence source** — how a project's before/after comparison is or will
  be obtained: `satellite` (has a GPS coordinate), `manual_upload`
  (contractor-supplied photos), or `unavailable` (neither yet).
