# Quickstart — Get This Running

## Before you start

You need `python3` (3.10+), `node` (18+) and `npm` installed, plus internet
access — every project's analysis is a real Sentinel-2 fetch, there's no
offline/bundled-image mode. No database server to install, no dataset to
download by hand, no account to create first.

## Folder layout — this part matters

`start-all.sh` expects **InfraWatch** and **satellite-service** to be sibling
folders under the same parent directory:

```text
some-parent-directory/
├── InfraWatch/            <- this repo
└── satellite-service/     <- the separate microservice repo
```

If `satellite-service` isn't there, `./start-all.sh` fails immediately with a
clear error telling you what to fix, instead of a confusing error mid-setup.

## The one command

From inside `InfraWatch/`:

```bash
./start-all.sh
```

First run does full setup automatically: creates Python virtualenvs for the
backend and satellite-service, installs backend/frontend/satellite-service
dependencies, and writes working `.env`/`.env.local` files from the
`.env.example` templates. This can take a few minutes. Every run after that
starts in seconds.

On first boot, the backend automatically seeds itself — nothing to prepare
by hand:

- 4 real legacy projects with real manually-photographed before/after
  evidence, sourced from a real ~1,000-row MPLADS works CSV
  (`backend/data/processed/mplads_normalized.csv`) — only the 3 rows in that
  CSV with a verified GPS coordinate become registry entries; the other 997
  have no coordinate and no real progress figure at all, so they're kept as
  reference data on disk rather than imported as ~1,000 misleading "0%
  progress" rows (see [MERGE-NOTES.md](MERGE-NOTES.md))
- one demo analyst account and one demo contractor account

This seeding is guarded so it only ever runs against a genuinely empty
database — restarting the backend, or re-running `docker-compose up` against
an existing volume, never re-seeds or wipes real data.

A 24-project real PMGSY facility-location sample also imports itself in the
background on first run (needs internet, ~5-10 minutes) — see
`/tmp/infrawatch-logs/pmgsy-import.log`.

Once it's up:

```text
Dashboard:               http://localhost:3000
Backend API docs:        http://localhost:8000/docs
satellite-service docs:  http://localhost:8001/docs
```

Give it 30-60 seconds on first run to finish starting all three services.
Press `Ctrl+C` in the terminal running `start-all.sh` to stop everything
cleanly.

### Demo accounts (seeded automatically — evaluation only, never reuse in production)

| Role | Email | Password |
|---|---|---|
| Analyst | `analyst@infrawatch.local` | `demo-analyst-2025` |
| Contractor | `contractor@infrawatch.local` | `demo-contractor-2025` |

Sign in as the analyst to browse the full registry, or as the contractor to
register a new project or upload evidence. You can also register your own
account from `/register` — pick either role.

## How analysis actually works

Every coordinate-based project is analyzed by satellite-service, which
fetches actual Sentinel-2 10m band imagery via a public STAC catalog and
runs the real PlanAura change-detection model. This needs internet access;
first analysis per project takes roughly 10-30 seconds. Projects with no
GPS coordinate (real bulk-imported government records commonly have none)
are instead screened from contractor-uploaded before/after photos, scored
by that same real model via a different endpoint — see
[01-project-overview.md](01-project-overview.md) for the full picture.

## Something went wrong — now what?

Logs for all three services are written under `/tmp/infrawatch-logs/`
(`backend.log`, `frontend.log`, `satellite-service.log`, and
`pmgsy-import.log`). Check those first.

Common issues:

- **"could not find ../satellite-service"** — clone `satellite-service` as a
  sibling folder next to `InfraWatch/` (see Folder layout above).
- **Port already in use** — `start-all.sh` kills anything already listening
  on 8000/8001/3000 before starting; if that fails, find and stop the
  process manually (`lsof -ti tcp:8000`).
- **Login/register calls hang or time out** — confirm the backend is
  actually up (`curl http://localhost:8000/api/health`) and that
  `frontend/.env.local`'s `NEXT_PUBLIC_API_BASE_URL` points at it.

## What NOT to do

- Don't reuse the demo account passwords, or `JWT_SECRET_KEY`'s
  development default, anywhere reachable outside your own machine.
- Don't expect instant results — a live Sentinel-2 fetch and model run
  takes real seconds, not milliseconds.

## I want to understand what I'm running, not just start it

Read [01-project-overview.md](01-project-overview.md) next.
