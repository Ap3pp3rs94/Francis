# Francis Worker 3 - Voice Receipts And ElevenLabs Boundary

You are Worker 3 in a four-terminal Francis build run.

Primary lane: voice-to-substrate receipts, ChatGPT voice bridge, and ElevenLabs
boundary truth.

Read first:

1. `AGENTS.md`
2. `docs/operations/COMPLETION_LEDGER.md`
3. `docs/operations/ORB_CONTINUUM_STATE.md`
4. `docs/operations/COMPLETION_MODEL.md`
5. `docs/canonical/BUILD_MANIFEST.md`

Non-negotiable lock:

- Do not change the Orb appearance.
- Do not connect ElevenLabs directly to Orb animations or desktop controls.
- Voice enters Francis. Francis creates governed substrate state. The Orb only
  represents that real state.
- Do not hardcode or print secrets.
- Do not enable always-on listening by default.

Current repo truth to preserve:

- ChatGPT voice ingress can record transcript receipts and queue bounded
  Orb-position commands.
- ElevenLabs is the user's preferred output voice provider, but live provider
  use must remain configuration-driven and receipt-backed.
- Transcript unavailable and unavailable provider states must remain truthful.

Bounded task:

Improve the smallest voice receipt, provider-boundary, or replay/readback gap
available now. Good slices include receipt linkage, provider unavailable status,
redaction, replay fields, public MCP proof clarity, or tests that prevent voice
from bypassing mission/governance state.

Allowed primary files:

- `src/francis/chatgpt_voice_bridge.py`
- `src/francis/mcp_gateway/**`
- `scripts/chatgpt-voice-*.ps1`
- `scripts/orb-voice-overlay-lens-validation.ps1`
- `tests/test_chatgpt_voice_bridge.py`
- `tests/test_chatgpt_voice_*`
- `tests/test_orb_voice_overlay_lens_validation_script.py`
- `docs/operations/ORB_CONTINUUM_STATE.md`
- `docs/operations/COMPLETION_LEDGER.md`

Acceptance criteria:

- Voice input/output produces or attaches to structured receipts.
- Live, mock, fixture, replay, unavailable, and unconfigured paths cannot be
  confused.
- Secrets are redacted.
- No voice path directly controls the Orb outside the governed bridge/overlay
  request contract.
- Focused tests pass.

Do not:

- Store API keys.
- Make purchases or external account changes.
- Claim live ElevenLabs output unless actually produced.
- Restart Continuum.
- Commit or push.

Final response format:

STATUS
FILES CHANGED
WHAT CHANGED
WHY
VALIDATION
RISKS / FOLLOW-UPS

Also include completion percentages only as evidence claims. Overall Francis and
current build-phase percentages do not move unless a ledger-backed gate actually
closed.
