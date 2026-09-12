# Quickstart — Get This Running in Under 5 Minutes

**Read this first.** This is the only doc you need to actually get the
project running. Everything else in `docs/` is background reading for once
it's already up — don't start there.

There is exactly **one command** to run. You do not need to create a
database, download any dataset, or configure anything by hand — all of that
happens automatically the first time you run it.

## Before you start

You need three things installed on your machine:
- **Python 3.10+** — check with `python3 --version`
- **Node.js 18+** — check with `node --version`
- **Git** (to have cloned the repos in the first place)

If any of those commands fail ("command not found"), install that one thing
first, then come back here. Nothing else needs installing by hand — the
script below installs every Python/Node dependency itself.

## Folder layout — this part matters

You need **two folders, sitting next to each other** (same parent folder):

```
some-folder-you-choose/
├── InfraWatch/            ← this repo
└── satellite-service/     ← the other repo
```

If you only cloned `InfraWatch`, go get `satellite-service` too and put it
right next to it, not inside it. The startup script looks for
`../satellite-service` relative to this repo — if that folder isn't there,
it'll tell you exactly that instead of failing mysteriously.

## The one command

Open a terminal, go into the `InfraWatch` folder, and run:

```bash
./start-all.sh
```

That's it. First time you run it, it'll take a few minutes (installing
everything). Every time after that, it starts in seconds.

When it's ready, you'll see three URLs printed. Open the first one:

- **http://localhost:3000** ← the actual dashboard, open this in your browser
- http://localhost:8000/docs (backend API, only if you're curious)
- http://localhost:8001/docs (satellite microservice API, only if you're curious)

You'll see a dashboard with 6 sample projects already loaded, a map, and
KPI cards — **nobody had to create that data by hand**, the backend creates
it automatically the moment it starts up.

**To stop everything**: go back to that terminal and press `Ctrl+C`. It
shuts down all three services cleanly.

## Two modes — which one do I want?

```bash
./start-all.sh          # demo mode (default) — bundled sample images, works
                         # with no internet, cannot fail, use this for your
                         # first run and for any offline demo/presentation

./start-all.sh real     # real mode — every project gets analyzed against
                         # actual live Sentinel-2 satellite imagery. Needs
                         # internet access. This is the "real" feature —
                         # use this once you want to show the actual AI
                         # pipeline working, not just the UI.
```

You can switch between them any time — just stop (`Ctrl+C`) and re-run with
the other argument. Nothing needs to be reset or cleaned up in between.

## Something went wrong — now what?

1. **Read the actual error message the script printed.** It's usually
   exactly what's wrong (e.g. "satellite-service not found" means the
   folder layout above isn't right).
2. Check the log files it mentions, under `/tmp/infrawatch-logs/` — this
   shows you the real error from whichever of the three services is
   unhappy, not just "something broke."
3. If a port is already in use (you ran this before and it's still
   running somewhere) — go find that terminal and press Ctrl+C there
   first, or just close that terminal window.
4. Still stuck? See the **Troubleshooting** section at the bottom of
   [03-developer-setup.md](03-developer-setup.md) — it lists the specific
   failure modes we've actually hit while building this and how to fix each
   one. Don't guess — that doc was written from real mistakes, not
   hypothetical ones.

## What NOT to do

- Don't manually create a database, don't manually download any satellite
  imagery, don't manually add the 6 demo projects — all of that is
  automatic. If you find yourself trying to do any of that by hand, stop —
  something else is wrong and you're compensating for it, not fixing it.
- Don't edit `.env` files unless a doc specifically tells you to for a
  specific reason. The defaults are already correct.
- Don't run `pip install` or `npm install` yourself outside of
  `./start-all.sh` (or the individual `./setup.sh` scripts, same thing) —
  if dependencies are missing, re-running the script fixes it; installing
  things ad hoc is how environments get into a state nobody can reproduce.

## I want to understand what I'm running, not just start it

Once it's up and you've clicked around, come back and read, in order:
[01-project-overview.md](01-project-overview.md) →
[02-user-guide.md](02-user-guide.md) →
[03-developer-setup.md](03-developer-setup.md) (this has the manual,
step-by-step version of what `start-all.sh` does automatically, in case you
ever need to run one piece on its own) →
[04-testing-and-qa.md](04-testing-and-qa.md) →
[05-architecture-and-api-reference.md](05-architecture-and-api-reference.md).
