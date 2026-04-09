export type InterjectReason =
  | "missing_required_field"
  | "low_confidence"
  | "confirmation_required"
  | "approval_required"
  | "conflicting_intent"
  | "permission_blocked"
  | "policy_blocked"
  | "unsafe_action";

export interface InterjectionDecisionInput {
  confidence: number;
  missingRequiredField: boolean;
  confirmationRequired: boolean;
  approvalRequired?: boolean;
  conflictingIntent: boolean;
  permissionBlocked: boolean;
  policyBlocked?: boolean;
  unsafeAction: boolean;
}

export interface InterjectionDecision {
  interject: boolean;
  reason?: InterjectReason;
}
