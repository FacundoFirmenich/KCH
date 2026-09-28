# Research note — closure audit against catalogue misspecification

Gate 012 could stop after the first intervention when it selected the singleton INTERACTION route. That is efficient only if the catalogue is assumed correct. An off-class process with signature M×L is observationally identical to INTERACTION on the first intervention alone.

Gate 013 makes model-class closure a terminal obligation. The reference M×L run records that the parent would have stopped, gives that counterfactual zero evidentiary weight, audits the second coordinate, and returns MODEL_CLASS_BREAK.

Across 4,000 structured splice episodes, v2.2 produced zero false catalogue certifications and mean break rate 99.625%; the parent v2.1 comparator certified some catalogue member in 100% of those splice episodes. A continuous off-grid control p=(.30,.70) produced 76% break and 24% unresolved HOLD, with zero false certification in 1,000 episodes.

The robustness tax of this first implementation is severe and explicitly non-theorem: mean legal cost is 43.98x the v2.1 mean and mean declared risk 86.50x. The next research problem is therefore efficient sentinel allocation under the same fail-closed semantics.
