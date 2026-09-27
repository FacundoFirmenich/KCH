# Budgeted robust belief-tree planning

The experiment uses a binary hidden provenance condition, ten optional information probes, two critical certification probes and nine admissible ambiguity models. The robust planner chooses sensor `s3`; an optimistic nominal model chooses `s2`.

Across the nine fixed admissible models, robust-policy worst-case value is 0.660 versus 0.655 for the nominal policy. The rectangular Bellman certificate is 0.63948 because the adversary may select the worst admissible model locally at each state. An out-of-set control gives robust-policy value 0.565, below the certificate: the guarantee does not survive exclusion of the true model from the ambiguity set.
