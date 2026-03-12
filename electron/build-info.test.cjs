const test = require("node:test");
const assert = require("node:assert/strict");

const { buildIdentity } = require("./build-info");

test("build identity keeps packaged builds on semantic version only", () => {
  const info = buildIdentity({
    version: "0.1.0",
    packaged: true,
    revision: "abc1234",
  });

  assert.equal(info.distribution, "portable");
  assert.equal(info.identity, "0.1.0");
  assert.equal(info.revision, "abc1234");
});

test("build identity includes git revision for source builds", () => {
  const info = buildIdentity({
    version: "0.1.0",
    packaged: false,
    revision: "abc1234",
  });

  assert.equal(info.distribution, "source");
  assert.equal(info.identity, "0.1.0+abc1234");
});
