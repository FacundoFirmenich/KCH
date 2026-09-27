# Mathematical results

For ambiguity models m in M, the rectangular robust Bellman operator is

V_h(s)=max{stop(s), max_a[-c(a)+min_{m in M(s)} sum_o P_m(o|s,a)V_{h-1}(s_{a,o})]}.

The bounded planner maintains feasible lower bounds and optimistic upper bounds. A root action is promoted only when its lower bound exceeds every competing upper bound and its own value interval is closed within epsilon; otherwise it returns `ABSTAIN_UNCERTIFIED`.

Executed instance: exhaustive exact planning visits 4077 cached states. Static action bounds plus bounded recursion certify the same exact action/value using 109 memo states, 65 expanded states and 568 static prunes. This is an exact finite-instance certificate, not a general complexity theorem.
