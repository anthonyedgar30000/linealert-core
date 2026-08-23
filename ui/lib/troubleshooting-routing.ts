export type TroubleshootingFault =
  | "alignment"
  | "folds"
  | "stretch"
  | "bubbles"
  | "multiple";

export type TroubleshootingRole =
  | "operator"
  | "senior-operator"
  | "millwright"
  | "maintenance"
  | "technician"
  | "qa"
  | "engineering"
  | "plant-manager";

export type TroubleshootingRoute = {
  profileId: "speedway-labeler-troubleshooting-v1";
  profileVersion: 1;
  decision: "ROUTE";
  reasonCode: "LINEALERT.TROUBLESHOOTING_ROUTE_SELECTED";
  procedureId: string;
  firstCheck: string;
  roleInstruction: string;
  authorizedAction: false;
};

const procedures: Record<
  TroubleshootingFault,
  { procedureId: string; firstCheck: string }
> = {
  alignment: {
    procedureId: "LABEL_ALIGNMENT_OFF",
    firstCheck: "Inspect Lane B release",
  },
  folds: {
    procedureId: "LABEL_FOLDS",
    firstCheck: "Inspect belt contact",
  },
  stretch: {
    procedureId: "LABEL_STRETCH_LINES",
    firstCheck: "Verify web tension",
  },
  bubbles: {
    procedureId: "LABEL_BUBBLES",
    firstCheck: "Inspect applicator pressure",
  },
  multiple: {
    procedureId: "MULTIPLE_LABELS",
    firstCheck: "Inspect gap sensor condition",
  },
};

const roleInstructions: Record<TroubleshootingRole, string> = {
  operator: "Perform the displayed inspection only; do not adjust outside operator scope.",
  "senior-operator": "Confirm the inspection result and preserve any justified override.",
  millwright: "Localize the mechanical relationship before adjustment.",
  maintenance: "Review the bounded procedure and intervention history.",
  technician: "Compare controller intent with the verified physical response.",
  qa: "Verify the defect against the active sampling plan.",
  engineering: "Review the envelope and evidence before changing the model.",
  "plant-manager": "Assign the next qualified owner; do not diagnose the machine.",
};

export function resolveSyntheticTroubleshootingRoute(
  fault: TroubleshootingFault,
  role: TroubleshootingRole,
): TroubleshootingRoute {
  const procedure = procedures[fault];
  return {
    profileId: "speedway-labeler-troubleshooting-v1",
    profileVersion: 1,
    decision: "ROUTE",
    reasonCode: "LINEALERT.TROUBLESHOOTING_ROUTE_SELECTED",
    procedureId: procedure.procedureId,
    firstCheck: procedure.firstCheck,
    roleInstruction: roleInstructions[role],
    authorizedAction: false,
  };
}

export function liveEvidenceRouteBoundary(scope?: string): {
  decision: "REFUSE" | "UNOBSERVED";
  reasonCode: string;
} {
  if (!scope) {
    return {
      decision: "UNOBSERVED",
      reasonCode: "EVIDENCE.TROUBLESHOOTING_LIVE_SCOPE_UNOBSERVED",
    };
  }
  return {
    decision: "REFUSE",
    reasonCode: "EVIDENCE.TROUBLESHOOTING_SCOPE_INADMISSIBLE",
  };
}
