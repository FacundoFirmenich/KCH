# Minimal intervention design and identifiability frontier

For hypotheses H and admissible interventions A, each intervention induces a separation set S_a of hypothesis pairs with different predictive distributions. Minimum-cost identification solves

min sum_a c_a z_a

subject to every target pair being hit by at least one selected S_a. Pairs outside the union of authorized separation sets are not optimization failures; they define the residual identifiability equivalence relation.

In the transported v1.9 quotient, 117 syntactic programs collapse to five full-domain predictive signatures with multiplicities 38,34,1,34,10. Observational support x=z leaves 6,786 syntactic pairs unresolved; one off-support intervention leaves 3,502; both leave 1,870, which are globally prediction-equivalent over all binary x,z interventions in the declared domain.

Frozen cost-aware counterexample: exact T0,T3,T4 costs 5.2; greedy newly-separated-pairs-per-cost chooses T3,T2,T0,T4 and costs 6.7.
