export type InterjectReason =
  | "missing_required_field"
  | "low_confidence"
  | "confirmation_required"
  | "conflicting_intent"
  | "permission_blocked"
  | "unsafe_action";

export interface InterjectionDecisionInput {
  confidence: number;
  missingRequiredField: boolean;
  confirmationRequired: boolean;
  conflictingIntent: boolean;
  permissionBlocked: boolean;
  unsafeAction: boolean;
}

export interface InterjectionDecision {
  interject: boolean;
  reason?: InterjectReason;
}
