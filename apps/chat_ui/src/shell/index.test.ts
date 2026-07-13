import assert from "node:assert/strict";
import test from "node:test";

import { francisSurfaceForPath, francisSurfaceHref, normalizeFrancisSurfacePath } from "./index.ts";

test("normalizes root and trailing slashes", () => {
  assert.equal(normalizeFrancisSurfacePath(""), "/");
  assert.equal(normalizeFrancisSurfacePath("/frontend/"), "/frontend");
  assert.equal(normalizeFrancisSurfacePath("/backend///"), "/backend");
});

test("maps explicit pages and preserves diagnostics as the backend alias", () => {
  assert.equal(francisSurfaceForPath("/"), "frontend");
  assert.equal(francisSurfaceForPath("/frontend"), "frontend");
  assert.equal(francisSurfaceForPath("/backend"), "backend");
  assert.equal(francisSurfaceForPath("/diagnostics"), "backend");
});

test("returns canonical surface hrefs", () => {
  assert.equal(francisSurfaceHref("frontend"), "/frontend");
  assert.equal(francisSurfaceHref("backend"), "/backend");
});
