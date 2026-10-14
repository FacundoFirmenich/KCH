package csc.kch.support

default decision := {"result": "DENY", "reason": "NO_MATCHING_RULE", "requested_decision": "DENY", "authority_granted": false, "execution_granted": false}

rule_0_workspace_read if {
  input.action_type == "TOOL_CALL"
  startswith(input.resource, "kwan://workspace/")
  input.effect_class in {"E0_READ_ONLY"}
  input.risk_milli <= 100
  input.cost_milli <= 100
  input.authority_granted == false
  input.execution_granted == false
}

decision := output if {
  rule_0_workspace_read
  output := {"result": "SUPPORT", "reason": "RULE:workspace-read", "requested_decision": "APPLY", "authority_granted": false, "execution_granted": false}
}

rule_1_liveops_noncritical_dispatch if {
  input.action_type == "DISPATCH_LOCAL_COMMAND"
  startswith(input.resource, "liveops:zone:")
  input.effect_class in {"E1_REVERSIBLE_LOCAL"}
  input.risk_milli <= 200
  input.cost_milli <= 200
  input.authority_granted == false
  input.execution_granted == false
  input.context["severity"] == "NON_CRITICAL"
}

decision := output if {
  rule_1_liveops_noncritical_dispatch
  output := {"result": "SUPPORT", "reason": "RULE:liveops-noncritical-dispatch", "requested_decision": "APPLY", "authority_granted": false, "execution_granted": false}
}
