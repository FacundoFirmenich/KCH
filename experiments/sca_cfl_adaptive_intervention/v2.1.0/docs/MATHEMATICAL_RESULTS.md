# Mathematical results — gate 012

Stage 1 samples only `do(x=0,z=1)` and certifies one route among LOW, MID, HIGH at likelihood-ratio threshold 80. Under the true route, each wrong-route LR is a nonnegative martingale; Ville gives crossing probability <=1/80. Union over the two wrong routes gives <=0.025.

MID is singleton INTERACTION and stops. LOW/HIGH enter stage 2, which samples only `do(x=1,z=0)` and certifies one of two hypotheses at LR threshold 40, for wrong-pair probability <=1/40=0.025. Total misidentification probability is therefore <=0.05 by union bound, conditional on the declared five-class model and predeclared protocol.

Safety and authority are checked before every observation. A blocked or cancelled intervention creates no synthetic observation and contributes zero likelihood.
