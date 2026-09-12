# User Guide — For Field Officers, Reviewers & Demo Audiences

This guide is for people **using** the InfraWatch dashboard, not building
it. No technical background needed. If you want to know what's happening
under the hood, see [01-project-overview.md](01-project-overview.md); if you
need to install or run anything, see
[03-developer-setup.md](03-developer-setup.md) instead.

## Opening the dashboard

Go to the URL your team gives you (locally, this is usually
`http://localhost:3000`). You'll land on the main dashboard.

## What you see on the dashboard

**Top KPI cards** — four numbers at a glance:
- **Total Projects** — how many projects are being monitored
- **Normal Progress** — projects where reported progress and satellite
  evidence agree
- **Medium Priority** — projects worth a routine review
- **Least Priority** — projects flagged for field verification (the reported
  progress and what the satellite sees don't match up)

**The map** — every project plotted as a colored pin:
- 🔴 **Red** — Least priority / field verification recommended
- 🟡 **Yellow** — Medium priority / review recommended
- 🟢 **Green** — Normal, no discrepancy flagged

Click any pin for a quick preview card (location, reported progress, a
satellite thumbnail) with a button straight into the full analysis.

You can switch the basemap between **Map** (roads/labels) and **Satellite**
(imagery) using the toggle in the map's top-right corner, and turn the
**Changes** overlay on/off (this shows the AI's flagged change regions as
colored boxes directly on the map, once a project has been analyzed).

**The project table** below the map lists every project with search (by
name or sector) and filter controls (by priority level or sector). Click
any project name, or its **Analyze →** button, to open the full detail
view.

## The project detail page

Opening a project runs (or re-runs) its satellite analysis automatically —
this can take anywhere from instant (if bundled demo images are used) to
10-30 seconds (if it's fetching real Sentinel-2 imagery for the first time).

You'll see:

1. **Header strip** — project name, priority badge, ID, coordinates, sector.
2. **Fetch Latest Sentinel-2 (STAC)** button — forces a fresh real-imagery
   fetch even for a demo project (only meaningful when the backend is
   running in `real` satellite mode — ask a developer if you're not sure).
3. **Four metric cards** — reported progress (the official claim), approved
   budget, and the dates of the two satellite scenes actually used (T1
   baseline / T2 latest observation).
4. **Project Scope** — the plain description of what the project is.
5. **Three tabs**:
   - **AI Satellite Screening** (default) — the main event, see below.
   - **Milestones** — the planned schedule (phase dates and expected %).
   - **Financials** — money disbursed so far, by category and date.

### Reading the "AI Satellite Screening" tab

- **Before / after comparison slider** — the two actual satellite photos,
  drag the center handle left/right to reveal one underneath the other.
  This is the ground truth the whole analysis is based on — always worth a
  quick look yourself. If the model flagged any change regions, they're
  drawn as highlighted boxes on top of both images — hover one to see its
  type, confidence, and estimated area.
- **Export Report (PDF)** button (top of the page) — downloads a
  self-contained PDF summarizing everything on this tab (project info,
  both satellite images, the AI summary, the recommendation, and a table of
  every detected change region) — useful for attaching to a field
  verification case file or sharing with someone who doesn't have dashboard
  access. Needs a completed analysis first (the button is disabled until
  one exists).
- **AI Confidence** — how strongly the model believes its own read of the
  imagery (not a probability of fraud, just "how sure is this
  measurement").
- **Summary line** — a one-sentence, plain-English description of what
  changed (or didn't).
- **Detected Change Categories** — if something changed, a breakdown of what
  kind (new construction, vegetation loss, etc.) with a confidence per item.
- **The recommendation banner** — the actual verdict:
  - *"No significant discrepancy"* — reported progress and observed change
    line up; no action needed.
  - *"Review recommended"* — some mismatch, worth a routine look.
  - *"Field verification recommended"* — the strongest flag: high claimed
    progress with little to no visible change. **This is the signal a field
    officer should act on first.**
- **Interactive map** — the same location, now with the flagged change
  regions drawn as colored boxes (click one for details: type, confidence,
  estimated area).

## What to actually do with a "Field verification recommended" flag

This is a **screening signal, not proof**. Before escalating anything:
- Look at the before/after images yourself — does the mismatch look
  believable, or could it be explained by clouds, shadows, or the picture
  quality?
- Check the scene dates — if T1 and T2 are very close together, of course
  little will have changed yet; that's not suspicious.
- Treat this as "worth sending someone to check," not "this project is
  fraudulent." The system is explicitly designed to never make that claim
  itself — see the disclaimer in the site footer.

## Frequently asked questions

**"No significant change regions were detected between the two scenes" — is
that a bug?**
No. It means the model's comparison of the two dates genuinely found little
visible difference. For a short time gap or a site that hasn't started
construction yet, that's the correct, honest answer — not every project
should show change.

**Why does the AI model name say "template-fallback" instead of Gemini?**
No Gemini API key is configured on this deployment. The measurement itself
is unaffected — only the wording of the summary comes from a fixed template
instead of an LLM. Ask a developer if you expect Gemini to be enabled here.

**A project shows no images at all.**
This means no satellite imagery could be found for that location (often:
too much cloud cover in the search window, or the location has no
Sentinel-2 coverage). The system will say so explicitly in the explanation
text rather than silently failing.

**Can I add a new project to check?**
Not directly from this UI yet — ask a developer to add it via the database
or (for satellite-service) a CSV batch upload. See
[03-developer-setup.md](03-developer-setup.md).
