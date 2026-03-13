const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");

const { buildIdentity, resolvePackagedDistribution } = require("./build-info");

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

test("build identity can preserve installer distribution for packaged builds", () => {
  const info = buildIdentity({
    version: "0.1.0",
    packaged: true,
    distribution: "installer",
    revision: "abc1234",
  });

  assert.equal(info.distribution, "installer");
  assert.equal(info.identity, "0.1.0");
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

test("packaged distribution resolves to installer when an uninstaller is present", () => {
  const installRoot = fs.mkdtempSync(path.join(os.tmpdir(), "francis-overlay-install-"));
  const execPath = path.join(installRoot, "Francis Overlay.exe");
  fs.writeFileSync(path.join(installRoot, "Uninstall Francis Overlay.exe"), "", "utf8");

  assert.equal(resolvePackagedDistribution(execPath), "installer");
});
