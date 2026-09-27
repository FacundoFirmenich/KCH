# Learning the domain in which robustness may claim robustness

v1.6 solved a robust finite POMDP assuming the ambiguity family was given. v1.7 makes the ambiguity family itself a statistical object.

The design separates Bayesian posterior concentration, anytime-valid confidence-set retention, model-class diagnostics, and authority to alter the model contract.

Executed campaign: 25,000 outer-family Monte Carlo episodes produced maximum observed false-exclusion rate 0.034 at alpha=.05. The inherited 9-model core had maximum observed false-rejection rate 0.001 over 9,000 core-correct episodes. A reference true model outside the core but inside the outer family rejects the core at t=181 while remaining covered by the authority set. A stress model outside the outer family triggers model-class HOLD at t=269; fallback remains shadow until explicit authority.
