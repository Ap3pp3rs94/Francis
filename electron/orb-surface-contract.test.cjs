const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const htmlPath = path.join(__dirname, "..", "services", "hud", "app", "static", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");

test("orb window removes the persistent strip markup and does not regain legacy strip controls", () => {
  assert.doesNotMatch(html, /<div id="overlay-strip"/);
  assert.doesNotMatch(html, /id="orb-strip-stop"/);
  assert.doesNotMatch(html, /id="orb-strip-pause"/);
  assert.doesNotMatch(html, /id="orb-strip-open-chat"/);
  assert.doesNotMatch(html, /id="orb-strip-details"/);
  assert.doesNotMatch(html, /id="orb-strip-open-console"/);
});

test("shared renderer frames Lens as the operator-facing surface without review-shell copy drift", () => {
  assert.match(html, /Francis Lens HUD/);
  assert.match(html, /Operator overlay for live work\./);
  assert.match(html, /id="orb-context-open-chat"[\s\S]*>Chat<\/button>/);
  assert.match(html, /<strong>Francis Chat<\/strong>/);
  assert.match(html, /document\.title = orbWindowMode \? "Francis Orb" : "Francis Lens HUD";/);
  assert.doesNotMatch(html, />Review<\/button>/);
});

test("orb window runtime keeps an inline chat popup instead of forcing the review HUD", () => {
  assert.match(html, /function supportsOrbInlineConsole\(\)/);
  assert.match(html, /return !externalOrbMode;/);
  assert.match(html, /if \(orbWindowMode && !externalOrbMode\) {\s*openOrbCommandMenu\(\{ surface: "chat", focusComposer: true \}\);\s*return;\s*}/);
  assert.match(html, /dock\.dataset\.surfaceMode = menuSurfaceMode;/);
  assert.match(html, /usePostFX: false,/);
  assert.match(html, /root\.dataset\.renderer = "live";/);
});

test("orb window hard-removes the strip from the live UX and uses a right-click context menu instead", () => {
  assert.match(html, /body\[data-orb-surface="window"\] #overlay-strip \{\s*display: none !important;\s*pointer-events: none;\s*}/);
  assert.match(html, /function renderOrbOperatorStrip\(\) {\s*document\.body\.dataset\.orbAffordance = "hidden";\s*const strip = document\.getElementById\("overlay-strip"\);\s*if \(orbWindowMode\) {\s*if \(strip\) {\s*strip\.hidden = true;\s*strip\.style\.display = "none";\s*}\s*return;\s*}/);
  assert.match(html, /function resolveOrbAffordanceMode\(surfaceState\)/);
  assert.doesNotMatch(html, /body\[data-orb-surface="window"\]\[data-orb-affordance="visible"\] #overlay-strip/);
  assert.match(html, /root\.addEventListener\("contextmenu", \(event\) => {[\s\S]*openOrbCommandMenu\(\{ surface: "menu" \}\);/);
  assert.match(html, /root\.addEventListener\("dblclick", \(\) => {[\s\S]*openOrbCommandMenu\(\{ surface: "menu" \}\);/);
});

test("orb window keeps renderer scale restrained and restores the richer canvas treatment", () => {
  assert.match(html, /#orb-render-root \{\s*[\s\S]*width: 160px;\s*[\s\S]*height: 160px;/);
  assert.doesNotMatch(html, /#orb-render-root::before,\s*#orb-render-root::after \{\s*content: none;\s*display: none !important;\s*}/);
  assert.match(html, /#orb-render-root canvas \{\s*[\s\S]*drop-shadow\(0 22px 34px rgba\(0, 0, 0, 0\.3\)\)\s*[\s\S]*contrast\(1\.08\)\s*[\s\S]*saturate\(0\.9\);/);
  assert.doesNotMatch(html, /#orb-render-root\[data-body-state=/);
});

test("orb window keeps chat compact, orb-adjacent, and free of review-heavy support rows", () => {
  assert.match(html, /id="overlay-orb-menu"/);
  assert.match(html, /id="orb-context-open-chat"/);
  assert.match(html, /id="orb-context-pause"/);
  assert.match(html, /id="orb-context-stop"/);
  assert.match(html, /id="orb-context-hide"/);
  assert.match(html, /#overlay-dock\[data-surface-mode="menu"\] \{\s*width: min\(220px, calc\(100vw - 28px\)\);\s*max-height: min\(38vh, 260px\);\s*}/);
  assert.match(html, /#overlay-dock\[data-surface-mode="chat"\] \{\s*width: min\(340px, calc\(100vw - 32px\)\);\s*max-height: min\(56vh, 470px\);\s*}/);
  assert.match(html, /#overlay-dock\[data-surface-mode="menu"\] \.orb-chat-shell \{\s*display: none;\s*}/);
  assert.match(html, /#overlay-dock\[data-surface-mode="chat"\] \.orb-context-shell \{\s*display: none;\s*}/);
  assert.match(html, /#overlay-dock\[data-surface-mode="chat"\] \.orb-console-cards,\s*#overlay-dock\[data-surface-mode="chat"\] \.orb-chat-modes,\s*#overlay-dock\[data-surface-mode="chat"\] \.orb-chat-plan,\s*#overlay-dock\[data-surface-mode="chat"\] \.orb-diagnostics \{\s*display: none !important;\s*}/);
  assert.match(html, /#overlay-dock\[data-surface-mode="chat"\] #overlay-chat-meta \{\s*display: none;\s*}/);
  assert.match(html, /Chat opens here when you want Francis to do something\./);
  assert.match(html, /Ask and Francis replies here\./);
  assert.match(html, /placeholder="Ask Francis or give a bounded instruction"/);
  assert.match(html, /function positionOrbCommandSurface\(forceAnchor = false\)/);
  assert.match(html, /surfaceMode === "chat" \? "chat" : "menu"/);
  assert.match(html, /if \(bias === "chat"\) {\s*return resolveOrbChatPlacement\(anchorX, anchorY, safeWidth, safeHeight\);\s*}/);
});

test("orb window suppresses the thought bubble so chat stays the only surfaced popup", () => {
  assert.match(html, /const visible = Boolean\(\s*!orbWindowMode\s*&&\s*thought\s*&&\s*!orbCommandMenu\.open/);
  assert.match(html, /id="overlay-thought-bubble"/);
});

test("orb-only interaction entry points open inline chat instead of bouncing to the review HUD", () => {
  assert.match(html, /<button class="btn-primary" type="button" id="orb-context-open-chat" onclick="openOrbCommandMenu\(\{ surface: 'chat', focusComposer: true \}\)">Chat<\/button>/);
  assert.match(html, /openOrbCommandMenu\(\{ surface: "chat", focusComposer: true \}\);/);
  assert.match(html, /function openOrbChatFromThoughtBubble\(\) {[\s\S]*openOrbCommandMenu\(\{ surface: "chat", focusComposer: true \}\);/);
  assert.match(html, /if \(!supportsOrbInlineConsole\(\)\) {\s*openLensFromOrbSurface\(\)\.catch\(\(\) => {}\);\s*return;\s*}/);
  assert.match(html, /if \(!supportsOrbInlineConsole\(\)\) {\s*await openLensFromOrbSurface\(\);\s*return;\s*}/);
});

test("orb window suppresses denied interactivity claims while runtime health or ownership blocks them", () => {
  assert.match(html, /function noteSuppressedOrbOwnershipRequest\(reason, meta = {}\)/);
  assert.match(html, /runtimeHealth\.status !== "nominal"/);
  assert.match(html, /orbOwnershipRequestState\.lastSuppressedKey/);
  assert.doesNotMatch(html, /Francis Orb suppressed repeated interactivity request/);
});

test("orb sync ignores stale generation results after HUD/runtime epoch changes", () => {
  assert.match(html, /function getOrbSyncEpochKey\(\)/);
  assert.match(html, /function isOrbSyncEpochStale\(epochKey\)/);
  assert.match(html, /if \(isOrbSyncEpochStale\(requestEpoch\)\) {\s*return;\s*}/);
  assert.doesNotMatch(html, /Francis Orb ignored stale input sync result/);
  assert.doesNotMatch(html, /Francis Orb ignored stale perception result/);
});

test("orb ownership normalization carries explicit governor truth for the compact strip", () => {
  assert.match(html, /governorState: \[\s*"observe",\s*"assist",\s*"act",\s*"paused",\s*"degraded",\s*"user_override",\s*\]\.includes/);
  assert.match(html, /modeLabel: summarizeOrbSurfaceText\(raw\.modeLabel, "Observe"\)/);
  assert.match(html, /authorityLabel: summarizeOrbSurfaceText\(raw\.authorityLabel, "Pass-through"\)/);
  assert.match(html, /userOverrideActive: Boolean\(raw\.userOverrideActive\)/);
});

test("orb pass-through governor distinguishes hover claims from explicit surface focus and adds release hysteresis", () => {
  assert.match(html, /const ORB_INTERACTION_HIT_RADIUS_RATIO = 0\.34;/);
  assert.match(html, /const radius = Math\.min\(rect\.width, rect\.height\) \* ORB_INTERACTION_HIT_RADIUS_RATIO;/);
  assert.match(html, /const ORB_HOVER_INTERACTIVE_DELAY_MS = 320;/);
  assert.match(html, /const ORB_HOVER_RELEASE_DELAY_MS = 240;/);
  assert.match(html, /async function setOrbWindowInteractive\(interactive, requestReason = "orb_surface_hover"\)/);
  assert.match(html, /await setOrbWindowInteractive\(true, "orb_surface_focus"\);/);
  assert.match(html, /await setOrbWindowInteractive\(true, "orb_surface_hover"\);/);
  assert.match(html, /if \(\s*orbWindowInteractive\s*&&\s*orbHoverInteraction\.lastInsideAt > 0\s*&&\s*now - orbHoverInteraction\.lastInsideAt < ORB_HOVER_RELEASE_DELAY_MS\s*\)\s*{\s*return;\s*}/);
});

test("orb sync failures use bounded circuit buckets and keep raw diagnostics out of the primary strip", () => {
  assert.match(html, /function createOrbSyncBucket\(\) {\s*return {\s*failures: 0,\s*nextAllowedAt: 0,\s*circuitOpenUntil: 0,\s*loggedFailure: false,\s*diagnostic: "",\s*};\s*}/);
  assert.match(html, /const ORB_INPUT_SYNC_CIRCUIT_THRESHOLD = 4;/);
  assert.match(html, /const ORB_PERCEPTION_SYNC_CIRCUIT_THRESHOLD = 3;/);
  assert.match(html, /function getOrbSyncCircuitConfig\(channel = ""\)/);
  assert.match(html, /function isOrbSyncCircuitOpen\(bucket, nowMs = Date\.now\(\)\)/);
  assert.match(html, /function summarizeOrbSyncFailure\(channel,\s*{\s*disconnected = false,\s*circuitOpen = false,/);
  assert.match(html, /bucket\.nextAllowedAt = Math\.max\(\s*nowMs \+ getOrbSyncBackoffDelayMs\(bucket\.failures, baseDelay, channel\),\s*Number\(bucket\.circuitOpenUntil \|\| 0\),\s*\)/);
  assert.doesNotMatch(html, /console\.warn\(`Francis Orb .* sync degraded/);
  assert.match(html, /if \(orbSyncState\?\.input\?\.diagnostic\) {\s*lines\.push\(`sync\.input: \$\{orbSyncState\.input\.diagnostic\}`\);\s*}/);
  assert.match(html, /if \(orbSyncState\?\.perception\?\.diagnostic\) {\s*lines\.push\(`sync\.perception: \$\{orbSyncState\.perception\.diagnostic\}`\);\s*}/);
});

test("orb target cue rendering prefers richer attention semantics without breaking grounding contracts", () => {
  assert.match(html, /const attentionState = String\(targetCue\.attention_state \|\| ""\)\.trim\(\)\.toLowerCase\(\);/);
  assert.match(html, /const summary = String\(targetCue\.attention_summary \|\| targetCue\.summary \|\| fallbackText/);
  assert.match(html, /if \(!\["target_lock", "concrete"\]\.includes\(cueState\) \|\| surfaceKind !== "francis"/);
});

test("renderer degraded state stays calm and canonical when sync failures trip containment", () => {
  assert.match(html, /const detail = summarizeOrbSyncFailure\(channel, {\s*disconnected: disconnected \|\| nextStatus === "disconnected",\s*circuitOpen,\s*}\);/);
  assert.match(html, /detail,\s*failureCount: totalFailures,\s*consecutiveHealthy: 0,\s*lastFailureAtMs: nowMs,\s*lastChangedAtMs: nowMs,\s*nextProbeAtMs: bucket\.nextAllowedAt,\s*circuitOpenUntilMs: Number\(bucket\.circuitOpenUntil \|\| 0\),/);
  assert.match(html, /currentOrbPerception = {\s*\.\.\.currentOrbPerception,\s*state: "error",\s*summary: detail,/);
});

test("local safety posture flows into the orb body and secondary diagnostics instead of the primary strip copy", () => {
  assert.match(html, /interruptedActive: Boolean\(authority\?\.localStopped\)/);
  assert.match(html, /await refreshOrbSurfaceDesktopState\(bridge\);/);
  assert.match(html, /orbQuickChat\.status = "Panic stop degraded\. Inspect diagnostics\.";/);
  assert.match(html, /orbQuickChat\.status = "Pause failed\. Inspect diagnostics\.";/);
  assert.match(html, /if \(canonicalAuthority\?\.diagnostics\?\.localError\) {\s*lines\.push\(`authority\.local: \$\{canonicalAuthority\.diagnostics\.localError\}`\);\s*}/);
  assert.match(html, /if \(canonicalAuthority\?\.diagnostics\?\.remoteError\) {\s*lines\.push\(`authority\.remote: \$\{canonicalAuthority\.diagnostics\.remoteError\}`\);\s*}/);
});

test("orb window only forces resident anchoring for safety states and preserves live geometry otherwise", () => {
  assert.match(html, /desiredPoint: isOrbSafetyBodyState\(nextIntent\?\.state\)\s*\?\s*\{/);
  assert.match(html, /:\s*nextIntent\?\.desiredPoint,/);
  assert.match(html, /perchPoint: isOrbSafetyBodyState\(nextIntent\?\.state\)\s*\?\s*\{/);
  assert.match(html, /:\s*nextIntent\?\.perchPoint,/);
  assert.match(html, /targetPoint: isOrbSafetyBodyState\(nextIntent\?\.state\)\s*\?\s*null\s*:\s*nextIntent\?\.targetPoint,/);
  assert.match(html, /summary: isOrbSafetyBodyState\(nextIntent\?\.state\)\s*\?\s*String\(nextIntent\?\.summary \|\| "Holding a local operator safety posture\."\)\s*:\s*String\(nextIntent\?\.summary \|\| \(orbManualPerch\.active \? "Resting at your chosen perch\." : "Resting quietly at its resident perch\."\)\),/);
});

test("orb affordance stays hidden during boot and does not treat degraded health alone as an urgent slab trigger", () => {
  assert.match(html, /function resolveOrbAffordanceMode\(surfaceState\) {\s*if \(!orbWindowMode\) {\s*return "full";\s*}\s*return "hidden";\s*}/);
  assert.doesNotMatch(html, /surfaceState\?\.healthDegraded[\s\S]*return "urgent";/);
});

test("orb window clears persisted manual perch on launch so the orb returns to its resident live perch", () => {
  assert.match(html, /function loadOrbManualPerch\(\) {\s*if \(orbWindowMode\) {\s*orbManualPerch = { active: false, x: null, y: null };/);
  assert.match(html, /window\.localStorage\?\.removeItem\(ORB_MANUAL_PERCH_STORAGE_KEY\);/);
});

test("orb presentation prefers canonical execution summary and detail during live execution posture", () => {
  assert.match(html, /const executionSummary = String\(canonicalAuthority\?\.executionSummary \|\| ""\)\.trim\(\);/);
  assert.match(html, /const executionDetail = String\(canonicalAuthority\?\.executionDetail \|\| ""\)\.trim\(\);/);
  assert.match(html, /bodyState === ORB_BODY_STATES\.COMMIT_MOVE[\s\S]*bodyState === ORB_BODY_STATES\.INTERRUPTED[\s\S]*\? executionSummary/);
  assert.match(html, /bodyState === ORB_BODY_STATES\.COMMIT_MOVE[\s\S]*bodyState === ORB_BODY_STATES\.INTERRUPTED[\s\S]*\? executionDetail/);
});

test("orb policy posture is normalized upstream of the compact strip and renderer datasets", () => {
  assert.match(html, /const policy = currentOrbOperator\?\.policy && typeof currentOrbOperator\.policy === "object"/);
  assert.match(html, /String\(policy\?\.state \|\| ""\)\.trim\(\)\.toLowerCase\(\) === "approval_required"/);
  assert.match(html, /String\(policy\?\.state \|\| ""\)\.trim\(\)\.toLowerCase\(\) === "policy_blocked"/);
  assert.match(html, /root\.dataset\.policyState = String\(currentOrbOperator\?\.policy\?\.state \|\| "idle"\)\.trim\(\)\.toLowerCase\(\) \|\| "idle";/);
  assert.match(html, /overlay\.dataset\.policyState = String\(currentOrbOperator\?\.policy\?\.state \|\| "idle"\)\.trim\(\)\.toLowerCase\(\) \|\| "idle";/);
});

test("policy blocked approval copy stays concise without reintroducing wrapper-specific renderer styling", () => {
  assert.doesNotMatch(html, /#orb-render-root\[data-body-state="blocked"\]\[data-policy-state="policy_blocked"\]:not\(\.orb-hold\):not\(\.orb-handback\) canvas/);
  assert.match(html, /surfaceState\.approvalLabel \|\| "Approval needed"/);
  assert.match(html, /surfaceState\.policyBlocked\s*\?\s*"Policy blocked"/);
  assert.match(html, /surfaceState\.approvalDetail \|\| surfaceState\.detailLabel \|\| "Francis is paused and waiting for your explicit confirmation\."/);
});
