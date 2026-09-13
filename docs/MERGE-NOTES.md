# Merge Notes — What Happened to the New1 Branch's Work

This document explains what was carried forward from the `New1` branch into
the current `unified-platform` branch, what was left behind, and why —
written for anyone who contributed to `New1` and wants to understand where
their work ended up.

The short version: **the real assets from New1 are all here.** The dataset,
the photos, and several good UI ideas made it into this branch. What didn't
come forward was a set of specific code patterns that would have made the
product's core promise — an honest, unbiased screening signal — untrue in
practice, plus some housekeeping issues (dead code, hardcoded paths,
contradictory docs) that are worth knowing about but weren't the main
reason for the rewrite.

## What was kept

- **The real ~1,000-row MPLADS dataset.** `backend/data/processed/mplads_normalized.csv`
  — real government MPLADS/MoSPI records, the single most valuable thing
  New1 contributed. It's kept in the repo as reference data, but **not**
  bulk-imported wholesale: that CSV is a sanction/works registry, not a live
  construction tracker, and 997 of its 1,000 rows have no GPS coordinate and
  no real progress figure at all. Turning all 1,000 into individual
  "projects" would mean fabricating a misleading 0% progress for records
  that simply don't carry that data — which is exactly the kind of
  fabrication this rewrite exists to avoid. `backend/scripts/seed_real_mplads.py`
  instead pulls out only the 3 rows that DO have a verified coordinate (see
  next bullet) and seeds those automatically on every fresh boot.
- **The 4 real before/after photo sets for legacy projects with no GPS on
  record** — Goa Joggers Park, Goa Seraulim Crematorium, Nagaland Forest
  Colony Pond (all three also present as rows in the CSV, matched by
  `work_id`), and Tamil Nadu Udayarpalayam (a standalone real example not in
  the CSV). These live in `backend/app/manual_evidence/` and are wired up by
  `seed_real_mplads.py` to run through the real change-detection model on
  every fresh seed, the same as any other evidence upload would.
- **The 24-project real PMGSY facility-location sample** — real coordinates,
  importable via `backend/scripts/import_pmgsy_csv.py`.
- **UI ideas worth keeping** — the registry-table concept (serial numbers,
  work IDs, sector/status filtering, a searchable paginated table for a
  large real dataset), and the general shape of a before/after comparison
  view. These were reworked into the current `Dashboard.tsx` and
  `ProjectDetailView.tsx`, restyled to the current light-navy/gold-serif
  government aesthetic (the earlier violet/hot-pink look didn't read as a
  government tool and was replaced deliberately, not as a side effect of
  this rewrite).
- **The core idea of comparing reported vs. observed progress** as the
  central screening signal — that's still exactly what the risk engine's
  highest-weighted (50%) component does.

## What was deliberately not carried forward

**Hardcoded per-project-ID risk overrides.** New1's risk-scoring code
included functions along the lines of `check_manual_project(project_id)` and
`check_small_scale_exception(project_id)` that special-cased specific
project IDs to force a 0% risk score / "100% verified" outcome, regardless
of what the actual reported-vs-observed comparison computed for that
project. This is the one change that mattered most: a screening tool that
quietly exempts specific IDs from its own scoring isn't a screening tool
anymore, and any project ID added to that list (intentionally or by a
copy-pasted example) would have silently defeated the entire point of the
system for that project.

The current `app/risk_engine.py` is structured so this class of bug can't
recur by accident: none of its component-scoring functions accept a project
identifier as input at all —
`compute_satellite_discrepancy_risk(reported_progress, observed_change, ...)`
has no `project_id` parameter, which a dedicated test
(`test_satellite_discrepancy_no_hardcoded_project_ids`) enforces directly via
`inspect.signature`, so the absence is checked mechanically, not just
promised in a comment. If a specific real-world project genuinely needs
different treatment, that has to be expressed as different *input data* fed
into the same formula for everyone — never as a special case keyed to its ID.

**Duplicate and dead satellite pipelines.** New1 had accumulated more than
one code path attempting to do Sentinel-2 fetch + change detection, in
various states of being finished or abandoned, without a clear single
source of truth for which one actually ran in which mode. The current
architecture has exactly one real pipeline (the standalone
`satellite-service` microservice, called via
`app/satellite_service_client.py`) plus exactly one clearly-scoped fallback
(the legacy in-process OpenCV path, which now only ever runs for bundled
`[DEMO]` image pairs — see the branch comment in
`app/api/projects.py`'s `execute_pipeline()`). Anything that wasn't one of
those two was not carried forward.

**Hardcoded personal file paths.** Some scripts referenced absolute paths
specific to one contributor's machine, which would break for anyone else
who ran them. All scripts in this branch resolve paths relative to their
own file location (`Path(__file__).resolve().parents[...]`) so they work
the same way on any machine or in Docker.

**Self-contradicting documentation.** Some of New1's docs described
capabilities or guarantees ("verified," "fraud-detected") that the code
underneath didn't actually provide, or that directly contradicted the
scoring behavior described elsewhere in the same docs. That's part of why
this whole `docs/` folder and the root `README.md` were rewritten from
scratch against the current code rather than edited forward from the old
text — see the note at the top of this rewrite effort: prior docs were
treated as background only, not as a source of truth to copy claims from.

## Why this isn't a judgment on New1's intent

Fabricated debug/example code that special-cases a specific ID is a common
and understandable thing to leave in mid-development — it often starts as a
"let me force this one case to check the UI renders right" shortcut during
active debugging, not a deliberate attempt to mislead anyone. The reason it
couldn't stay is what it would have meant for the product if it had shipped
that way, not an assumption about how it got there. Nothing in this note is
meant to relitigate that — it's here so that if you go looking for where a
particular piece of New1's work ended up, you can find it (or find out
plainly why it didn't make the cut) without having to reconstruct the
history yourself.

If you contributed something to New1 that you don't see accounted for here
and believe should have carried forward, that's worth raising directly —
this document reflects what was reviewed and decided at the time of this
rewrite, not an exhaustive audit of every line New1 touched.
