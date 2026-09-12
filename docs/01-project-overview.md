# Project Overview — What InfraWatch Actually Is

Read this first if you're new to the project — a teammate, a judge, a
professor, or a future contributor. No prior context assumed.

## 1. The problem, in plain terms

India's MPLADS scheme (Members of Parliament Local Area Development Scheme)
funds local infrastructure projects — health centres, roads, schools, water
tanks — through government contractors. Contractors periodically self-report
how much progress they've made ("this road is 82% complete"). Nobody
routinely checks whether that number is true. A contractor can claim 82%
progress on a site that's barely been touched, and unless someone physically
visits, it can go unnoticed for months.

Physically inspecting every project is expensive and slow — there are far
more MPLADS projects than field officers who can visit them.

## 2. The idea: let satellites do the first pass

Every project has a location (latitude/longitude). Free satellite imagery
(Sentinel-2, from the European Space Agency, revisits nearly every point on
Earth every few days) can show what a site actually looks like now versus
what it looked like months ago. If a contractor claims 82% progress but a
satellite photo shows the same empty field as a year ago, that's worth a
field officer's attention. If the imagery shows a lot of new construction
matching the claim, that project can be deprioritized for manual checks.

**InfraWatch is not a fraud detector.** It never accuses anyone of anything.
It produces a screening signal — "this project's paperwork and its satellite
footprint disagree, go look at it" — for a human to act on. Every output is
phrased as a recommendation, never a finding.

## 3. How it actually works, end to end

For a given project (with a known location and a self-reported progress %):

1. **Fetch** two satellite photos of that location: an older "baseline" (T1)
   and the most recent available "observation" (T2), a few months to a year
   or more apart.
2. **Compare** them with a pretrained image-recognition model — not a human,
   not an LLM — to get a deterministic, reproducible measure of how much the
   site visibly changed, plus a rough guess at *what kind* of change (new
   construction vs. vegetation clearing vs. nothing).
3. **Narrate**: turn that measurement into a plain-English sentence ("no
   significant change detected" / "construction-like change detected across
   2 regions"). This step uses Google's Gemini when available, or a
   templated fallback when it isn't — either way the underlying measurement
   from step 2 is unaffected, only the wording changes.
4. **Compare against the claim**: if reported progress is high (≥70%) but
   observed change is low (<3%), flag "Field verification recommended". If
   both agree, mark it normal. Anything in between is "Review recommended".
5. **Display**: the dashboard map shows every project as a color-coded pin;
   drilling into one shows the before/after imagery, the AI's plain-English
   summary, and the flagged change regions plotted directly on the map.

## 4. The two codebases

This system is deliberately split into two separate projects that talk to
each other over HTTP, not one monolith:

| Project | What it is | Where |
|---|---|---|
| **InfraWatch** | The product: dashboard, map, project database, business rules (what counts as "field verification recommended"), demo data | `frontend/`, `backend/` (this repo) |
| **satellite-service** | A focused microservice that does only the satellite fetch + change-detection model + narration | sibling folder `../satellite-service` |

Why split them? So the satellite/ML piece can be worked on, tested, redeployed,
or eventually swapped for a better model, entirely independently of the
dashboard and business logic — and so a bug in one doesn't require
redeploying the other. See
[03-developer-setup.md](03-developer-setup.md) for exactly how to run both,
and satellite-service's own `docs/` for how that half works internally.

## 5. What's real vs. what's demo data

InfraWatch ships with 6 seeded "[DEMO]" projects so it has something to show
with zero setup. There are two independent modes, controlled by
`SATELLITE_MODE` in the backend's `.env`:

- **`demo`** (default): uses bundled sample before/after image pairs — no
  internet access needed, useful for offline demos or quick UI iteration.
- **`real`**: every project (including the seeded demo ones) is analyzed
  against actual, live Sentinel-2 imagery via satellite-service. This is
  what you want once you have real project coordinates to check.

Nothing about a project's name, budget, or reported progress is real data —
those are illustrative. What *can* be real is the satellite imagery and the
change measurement, once `SATELLITE_MODE=real` and a genuine project
location is supplied.

## 6. Current status (be honest about this in a demo)

**Working today**: the full pipeline above, running end to end against live
Sentinel-2 imagery, verified with real coordinates. Dashboard, map, project
detail, before/after imagery display, and the AI narration all work.

**Not yet done**:
- No authentication/roles — this is a local/trusted-network prototype, not
  internet-facing software.
- No labeled validation set — the "field verification recommended"
  thresholds are reasonable defaults, not tuned against ground truth.
- Not tested against a real MPLADS project dataset — only synthetic demo
  project records with real satellite lookups.
- No automated frontend tests (manual QA checklist exists instead — see
  [04-testing-and-qa.md](04-testing-and-qa.md)).

## Glossary

| Term | Meaning |
|---|---|
| **MPLADS** | The government scheme this prototype targets (SIH problem statement 26102) |
| **Sentinel-2** | Free ESA satellite constellation providing ~10m/pixel imagery, revisited every few days |
| **T1 / T2** | Baseline (older) / Observation (newer) satellite scene for a location |
| **STAC** | SpatioTemporal Asset Catalog — the standard API used to search for satellite scenes |
| **NDVI** | A vegetation index computed from red + near-infrared bands; used as a cheap "is this plant cover?" signal |
| **PlanAura** | This project's name for the pretrained-CNN change-detection model (see satellite-service's docs for the full explanation) |
| **GeoJSON** | Standard format for geographic shapes (here: the flagged change regions) that Leaflet/any map library can render directly |
