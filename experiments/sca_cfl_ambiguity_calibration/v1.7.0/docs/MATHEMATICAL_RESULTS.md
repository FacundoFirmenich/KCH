# Mathematical results

For a predeclared finite family M={m1,...,mK}, candidate mi is retained until the fixed-mixture Bayes factor
E_t^(i)=Q_-i(Y_1:t | A_1:t) / P_mi(Y_1:t | A_1:t)
crosses 1/alpha. Under mi and predictable actions, this is a nonnegative martingale of initial mean one; Ville's inequality gives anytime false-exclusion probability at most alpha.

For a null subfamily C, the composite monitor
E_t^C = Q(Y_1:t|A_1:t) / max_{m in C} P_m(Y_1:t|A_1:t)
is pointwise dominated by the likelihood ratio against the true m* whenever m* is in C. Therefore threshold crossing is anytime-valid by domination.

Failure to reject a subfamily is not proof of membership. Bayesian credible sets are SHADOW_ONLY. The authority set is the anytime-valid outer confidence set, conditional on the declared finite-family contract.
