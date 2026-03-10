import {
  InterjectionDecision,
  InterjectionDecisionInput,
} from "./types";

export class InterjectionPolicy {
  decide(input: InterjectionDecisionInput): InterjectionDecision {
    if (input.missingRequiredField) {
      return { interject: true, reason: "missing_required_field" };
    }

    if (input.permissionBlocked) {
      return { interject: true, reason: "permission_blocked" };
    }

    if (input.unsafeAction) {
      return { interject: true, reason: "unsafe_action" };
    }

    if (input.confirmationRequired) {
      return { interject: true, reason: "confirmation_required" };
    }

    if (input.conflictingIntent) {
      return { interject: true, reason: "conflicting_intent" };
    }

    if (input.confidence < 0.72) {
      return { interject: true, reason: "low_confidence" };
    }

    return { interject: false };
  }
}
