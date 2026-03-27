const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildSigningDoctor,
  loadWindowsCodeSigningCertificates,
  validateSigningDoctorReport,
} = require("./signing-doctor");

test("signing doctor blocks public release when only a self-issued local certificate is present", () => {
  const report = buildSigningDoctor({
    env: {
      FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: "Francis Overlay Dev Signing",
    },
    certificates: [
      {
        subject: "Francis Overlay Dev Signing",
        issuer: "Francis Overlay Dev Signing",
        thumbprint: "ABC123",
        hasPrivateKey: true,
        store: "Cert:\\CurrentUser\\My",
      },
    ],
    signingReport: {
      counts: {
        signed: 3,
      },
      artifacts: [
        { state: "signed" },
        { state: "signed" },
        { state: "signed" },
      ],
    },
  });

  assert.equal(report.status, "blocked");
  assert.equal(report.signedPackagingReady, true);
  assert.equal(report.publicReleaseReady, false);
  assert.ok(report.blockingReasons.includes("missing_publisher_hint"));
  assert.ok(report.blockingReasons.includes("self_issued_only"));
  assert.equal(
    report.suggestedPowerShell.machineLocalSignedBuild.env.FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME,
    "Francis Overlay Dev Signing",
  );
  assert.equal(
    report.suggestedPowerShell.machineLocalSignedBuild.env.FRANCIS_WINDOWS_SIGNING_SHA1,
    "ABC123",
  );
  assert.equal(report.suggestedPowerShell.publicReleaseCertStore.available, false);
  assert.equal(report.suggestedPowerShell.publicReleaseCertStore.reason, "self_issued_only");
});

test("signing doctor is ready when a matching public-trust certificate is available", () => {
  const report = buildSigningDoctor({
    env: {
      FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME: "Acme Software LLC",
      FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME: "Acme Software LLC",
    },
    certificates: [
      {
        subject: "Acme Software LLC",
        issuer: "Trusted Publisher CA",
        thumbprint: "DEF456",
        hasPrivateKey: true,
        store: "Cert:\\CurrentUser\\My",
      },
    ],
  });

  assert.equal(report.status, "ready");
  assert.equal(report.publicReleaseReady, true);
  assert.equal(report.blockingReasons.length, 0);
  assert.equal(report.certificates.matchingPublisherCandidates, 1);
  assert.equal(
    report.suggestedPowerShell.publicReleaseCertStore.env.FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME,
    "Acme Software LLC",
  );
  assert.equal(
    report.suggestedPowerShell.publicReleaseCertStore.env.FRANCIS_WINDOWS_SIGNING_SUBJECT_NAME,
    "Acme Software LLC",
  );
  assert.equal(
    report.suggestedPowerShell.publicReleaseCertStore.env.FRANCIS_WINDOWS_SIGNING_SHA1,
    "DEF456",
  );
});

test("signing doctor can normalize certificate rows returned from PowerShell JSON", () => {
  const certificates = loadWindowsCodeSigningCertificates({
    platform: "win32",
    shellCandidates: ["powershell.exe"],
    execFileSync: () =>
      JSON.stringify([
        {
          Subject: "CN=Acme Software LLC",
          Issuer: "CN=Trusted Publisher CA",
          Thumbprint: "def456",
          HasPrivateKey: true,
          Store: "Cert:\\CurrentUser\\My",
        },
      ]),
  });

  assert.deepEqual(certificates, [
    {
      subject: "CN=Acme Software LLC",
      issuer: "CN=Trusted Publisher CA",
      thumbprint: "DEF456",
      enhancedKeyUsage: "",
      hasPrivateKey: true,
      store: "Cert:\\CurrentUser\\My",
    },
  ]);
});

test("signing doctor validation fails closed when public signing is not ready", () => {
  const validation = validateSigningDoctorReport(
    {
      publicReleaseReady: false,
      blockingReasons: ["self_issued_only"],
    },
    {
      requirePublicReady: true,
    },
  );

  assert.equal(validation.ok, false);
  assert.deepEqual(validation.reasons, ["self_issued_only"]);
});

test("signing doctor validation passes when public signing is ready", () => {
  const validation = validateSigningDoctorReport(
    {
      publicReleaseReady: true,
      blockingReasons: [],
    },
    {
      requirePublicReady: true,
    },
  );

  assert.equal(validation.ok, true);
  assert.deepEqual(validation.reasons, []);
});

test("signing doctor surfaces an Azure template even when the current machine is blocked", () => {
  const report = buildSigningDoctor({
    env: {},
    certificates: [],
  });

  assert.equal(
    report.suggestedPowerShell.publicReleaseAzureTrustedSigning.env.FRANCIS_WINDOWS_SIGNING_PUBLISHER_NAME,
    "<legal publisher name>",
  );
  assert.match(
    report.suggestedPowerShell.publicReleaseAzureTrustedSigning.lines.join("\n"),
    /release:publish:windows:public/i,
  );
});
