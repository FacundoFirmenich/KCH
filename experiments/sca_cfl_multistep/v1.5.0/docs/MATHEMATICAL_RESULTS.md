# Mathematical Results — v1.5

Finite-horizon value:
V_h(psi)=max{-D(C(psi)), max_a[-lambda_c c(a)+sum_o P(o|psi,a)V_{h-1}(psi union {a=o})]}.

In the routing instance, horizon 2 selects a cheap routing probe with zero immediate gate effect. Expected raw acquisition cost is 0.22 versus 0.30 for the horizon-1/myopic policy; both reach terminal eligibility probability 1.

Adaptive submodularity requires Delta(a|psi)>=Delta(a|psi') for psi subset psi'. For the binary certification objective, Delta(B|empty)=0 while Delta(B|A=DISTINCT_ROOT)=0.8. Therefore the property is violated and no greedy guarantee based on adaptive submodularity is invoked. A modular coverage objective is an exhaustive positive control and passes.
