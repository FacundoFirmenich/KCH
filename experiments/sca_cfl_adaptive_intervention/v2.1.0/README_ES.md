# SCA/CFL Adaptive Intervention v2.1.0

Gate `ADAPTIVE_INTERVENTION_PROGRAMS_WITH_SAFETY_AND_COUNTERFACTUAL_STOPPING_012`.

Stage 1 samples only `do(x=0,z=1)` and certifies LOW={AND,X}, MID={INTERACTION}, or HIGH={Z,OR} with E=80. MID stops and cancels the parent static `do(x=1,z=0)` branch. LOW/HIGH enter Stage 2, where `do(x=1,z=0)` distinguishes the remaining pair at E=40.

Safety and authority are hard pre-observation gates. Cancelled/counterfactual interventions are append-only ledger facts with zero evidentiary weight.
