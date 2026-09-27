# Model-class discovery after ambiguity-set rejection

The inherited family contains 25 memoryless sensor-conditional Bernoulli models. The alternative synthetic DGP introduces dependence on the previous outcome.

Reference trajectory: inherited class rejects at t=423; discovery closes at t=600; the generator selects context depth 1 with posterior weight 0.9999963 and log-code gain 27.7155 over depth 0; on a fresh future stream the depth-1 candidate crosses e=20 after 58 observations.

Across 500 context-dependent episodes, class rejection occurs in 99.6%, structural proposal in 97.2%, and future certification in 97.2%. Across 1000 true-null episodes, outer rejection is 1.8%, with zero structural proposals. A forced fresh depth-1 certifier crosses in 17/2000 null streams (0.85%).

The result is synthetic and structural; it establishes governance and future-only certification, not causal truth or CFL Form status.
