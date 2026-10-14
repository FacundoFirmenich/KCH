// workspace-read: requested_decision=APPLY; SUPPORT ONLY
permit(principal, action, resource) when {
  context.action_type == "TOOL_CALL" &&
  context.resource like "kwan://workspace/*" &&
  (context.effect_class == "E0_READ_ONLY") &&
  context.risk_milli <= 100 &&
  context.cost_milli <= 100 &&
  context.authority_granted == false &&
  context.execution_granted == false
};

// liveops-noncritical-dispatch: requested_decision=APPLY; SUPPORT ONLY
permit(principal, action, resource) when {
  context.action_type == "DISPATCH_LOCAL_COMMAND" &&
  context.resource like "liveops:zone:*" &&
  (context.effect_class == "E1_REVERSIBLE_LOCAL") &&
  context.risk_milli <= 200 &&
  context.cost_milli <= 200 &&
  context.authority_granted == false &&
  context.execution_granted == false &&
  context.severity == "NON_CRITICAL"
};
