const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const htmlPath = path.join(__dirname, "orb-shell.html");
const html = fs.readFileSync(htmlPath, "utf8");

test("standalone orb shell keeps a smaller honest wrapper footprint and hides fallback ornament when the renderer is live", () => {
  assert.match(html, /#orb-frame \{\s*position: relative;\s*width: 400px;\s*height: 400px;/);
  assert.match(html, /#orb-fallback,\s*#orb-render-root \{\s*[\s\S]*width: 400px;\s*height: 400px;/);
  assert.match(html, /class="orb-ring ring-e"/);
  assert.match(html, /class="orb-ring ring-f"/);
  assert.match(html, /body\[data-renderer="live"\] #orb-fallback,\s*#orb-frame\[data-renderer="live"\] #orb-fallback \{\s*opacity: 0;\s*visibility: hidden;\s*}/);
});

test("standalone orb shell mounts the renderer without post FX so the transparent desktop path does not collapse into a black square", () => {
  assert.match(html, /orbApi = orbBundle\.createFrancisOrb\(root, \{[\s\S]*usePostFX: false,[\s\S]*enableBeam: false,/);
  assert.match(html, /root\.dataset\.renderer = "pending";/);
  assert.match(html, /frame\.dataset\.renderer = "pending";/);
  assert.match(html, /document\.body\.dataset\.renderer = "pending";/);
  assert.match(html, /root\.dataset\.renderer = "live";/);
  assert.match(html, /frame\.dataset\.renderer = "live";/);
  assert.match(html, /document\.body\.dataset\.renderer = "live";/);
});

test("standalone orb shell keeps wrapper-side canvas treatment minimal so the renderer owns the body look", () => {
  assert.match(html, /#orb-render-root canvas \{\s*[\s\S]*filter: drop-shadow\(0 10px 16px rgba\(0, 0, 0, 0\.16\)\);/);
  assert.match(html, /#orb-render-root\.orb-hold canvas \{\s*[\s\S]*drop-shadow\(0 0 10px rgba\(214, 93, 54, 0\.18\)\)\s*drop-shadow\(0 12px 18px rgba\(0, 0, 0, 0\.18\)\);/);
  assert.doesNotMatch(html, /#orb-render-root canvas \{[^}]*contrast\(/);
  assert.doesNotMatch(html, /#orb-render-root canvas \{[^}]*saturate\(/);
  assert.doesNotMatch(html, /#orb-render-root\.orb-hold canvas \{[^}]*brightness\(/);
});

test("standalone orb shell only claims the mouse from a smaller central hotspot after a hover dwell", () => {
  assert.match(html, /const ORB_INTERACTION_HIT_RADIUS_RATIO = 0\.34;/);
  assert.match(html, /const ORB_HOVER_INTERACTIVE_DELAY_MS = 320;/);
  assert.match(html, /const ORB_HOVER_RELEASE_DELAY_MS = 240;/);
  assert.match(html, /const radius = Math\.min\(rect\.width, rect\.height\) \* ORB_INTERACTION_HIT_RADIUS_RATIO;/);
  assert.match(html, /if \(now - orbHoverInteraction\.enteredAt >= ORB_HOVER_INTERACTIVE_DELAY_MS\) {/);
});
