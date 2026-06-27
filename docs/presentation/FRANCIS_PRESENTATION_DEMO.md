# Francis Presentation Demo

This is the truthful first presentation path for Francis. It is designed for
engineers, technical hiring managers, researchers, investors, enterprise
reviewers, and acquisition evaluators who need to see evidence without being
shown fake autonomy.

## What The Demo Proves

The demo proves three things that are already real in the repository:

1. Francis can read back its current build posture from the completion ledger
   and ORB build manifest.
2. Francis can run the governed MCP smoke path and refuse unapproved takeover or
   input attempts.
3. Francis can translate Orb operator intent into dry-run move, click, and type
   proposals with receipts while performing no live mouse or keyboard action.

This is a presentation demo, not a product readiness claim.

## Run It

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\francis-presentation-demo.ps1
```

The script writes a timestamped visual and evidence bundle under:

```text
.francis\presentation\demos\
```

That directory is ignored by git because it is runtime evidence, not source.

## What To Show

1. Open [README.md](../../README.md) and give the 30 second explanation:
   Francis is a local-first governed operator layer, not a chatbot wrapper.
2. Run the presentation script.
3. Open the generated `.html` visual report from
   `.francis\presentation\demos\`.
4. Use the generated Markdown report as the audit companion if someone wants
   the proof text.
5. Point to the completion-model readback:
   current phase, latest ledger entry, plane readiness, and open gaps.
6. Point to the MCP smoke readback:
   tool count, ready statuses, and unapproved action refusals.
7. Point to the Orb dry-run receipt paths:
   move, click, and type intents were proposed and receipted; live input stayed
   false.

## Optional Visual Setup

If the audience should also see the operator UI, run it separately:

```powershell
.\scripts\bootstrap.ps1 -IncludeChatUI
.\scripts\francis.ps1 api
```

In another terminal:

```powershell
cd apps\chat_ui
npm run dev
```

Open:

```text
http://localhost:5173
```

Only use the UI to show surfaces that are actually live. Do not imply the
presentation script depends on the UI; it does not.

## Allowed Claims

- Francis is an active engineering project with a ledger-backed build posture.
- Francis has a governed runtime spine with observable readbacks.
- Francis treats model output as proposal, not permission.
- Francis can produce Orb operator dry-run receipts for desktop intent.
- Francis refuses unapproved input/takeover paths in the MCP smoke check.

## Claims Not Allowed

- Do not claim Francis is a finished autonomous operator.
- Do not claim this demo performs live desktop input.
- Do not claim the Orb moved the physical cursor.
- Do not claim Stage 6, Stage 17, ORB Core, or full product readiness is closed.
- Do not claim collaboration tools or local models have independent authority.

## Audience Framing

For engineers:

- Focus on contracts, gates, receipts, and narrow validation.

For researchers:

- Focus on proposal versus execution, memory boundaries, and observable action
  traces.

For enterprise reviewers:

- Focus on local-first posture, refusal paths, auditability, and authority
  separation.

For investors or acquisition teams:

- Focus on category clarity: Francis is building the governed operator layer
  that sits between intent and action, not another chat surface.

## Recovery

If MCP smoke fails, rerun only the safe smoke command:

```powershell
.\.venv\Scripts\python.exe -m francis.mcp_gateway.smoke
```

If the Orb dry-run fails, rerun the existing narrow Orb proof:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\orb-operator-dry-run.ps1 -X 320 -Y 240 -Text "Francis presentation dry-run"
```

If either path fails, treat the failure as demo evidence. Do not hide it; the
truthful claim becomes that the presentation runner detected a broken governed
path before live authority was involved.
