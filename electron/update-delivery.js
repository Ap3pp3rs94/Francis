function buildUpdateDeliveryPosture({
  distribution = "source",
  buildIdentity = "unknown",
  update = null,
  rollback = null,
  signing = null,
  installRoot = null,
} = {}) {
  const channel = String(distribution || "source");
  const pendingNotice = Boolean(update?.pendingNotice);
  const rollbackCount = Number(rollback?.count || 0);
  const signingSeverity = String(signing?.severity || "low");

  let severity = "low";
  let summary = `Update posture for ${channel} is current.`;

  if (pendingNotice) {
    severity = "medium";
    summary = `Update review is pending for build ${String(update?.currentBuild || buildIdentity)}.`;
  } else if ((channel === "portable" || channel === "installer") && (signingSeverity === "high" || signingSeverity === "medium")) {
    severity = "medium";
    summary = String(signing?.summary || "Packaged distribution trust still needs review before updates are treated as routine.");
  } else if (channel === "source") {
    summary = "Source checkout updates stay manual and builder-driven.";
  } else if (channel === "installer") {
    summary = "Installer-managed updates are guided by a newer signed installer when available.";
  } else if (channel === "portable") {
    summary = "Portable updates are manual artifact replacement with explicit restart and review.";
  }

  const channelSummary =
    channel === "source"
      ? "Pull or merge the repo, rebuild the shell if packaging changed, then relaunch and review update posture."
      : channel === "installer"
        ? "Export shell posture if needed, close Francis Overlay, run the newer installer, relaunch, and review update posture."
        : "Export shell posture if needed, close Francis Overlay, replace the portable artifact, relaunch, and review update posture.";

  const rollbackSummary =
    rollbackCount > 0
      ? `${rollbackCount} rollback snapshot${rollbackCount === 1 ? "" : "s"} remain available if the new build does not settle cleanly.`
      : "No rollback snapshot is available yet. Create one before invasive update work.";

  const trustSummary =
    channel === "source"
      ? "Source checkouts rely on local repo trust and visible git identity."
      : signingSeverity === "low"
        ? "Packaged trust posture is current for this update path."
        : "Packaged trust remains review-first until Windows signing posture is explicit and current.";

  const steps = [
    channelSummary,
    rollbackSummary,
    pendingNotice
      ? "Review the update notice, schema summary, and repair path before treating continuity as settled."
      : "Review update discipline after relaunch only if the build identity or schemas changed.",
    trustSummary,
  ];

  const items = [
    {
      id: "channel",
      label: "Update Channel",
      summary: channelSummary,
    },
    {
      id: "rollback",
      label: "Rollback Readiness",
      summary: rollbackSummary,
    },
    {
      id: "trust",
      label: "Trust Path",
      summary: trustSummary,
    },
  ];

  return {
    severity,
    channel,
    summary,
    steps,
    items,
    cards: [
      {
        label: "Summary",
        value: summary,
        tone: severity,
      },
      {
        label: "Channel",
        value: channel,
        tone: channel === "source" ? "low" : "medium",
      },
      {
        label: "Build",
        value: String(update?.currentBuild || buildIdentity || "unknown"),
        tone: "low",
      },
      {
        label: "Pending Review",
        value: pendingNotice ? "yes" : "no",
        tone: pendingNotice ? "medium" : "low",
      },
      {
        label: "Rollback",
        value: rollbackCount > 0 ? `${rollbackCount} available` : "none",
        tone: rollbackCount > 0 ? "medium" : "low",
      },
      {
        label: "Signing",
        value: signingSeverity === "low" ? "current" : signingSeverity,
        tone: signingSeverity,
      },
      {
        label: "Install Root",
        value: installRoot || "source checkout",
        tone: installRoot ? "low" : "medium",
      },
    ],
  };
}

module.exports = {
  buildUpdateDeliveryPosture,
};
