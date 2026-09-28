# Mathematical results — gate 013

Let B_L, B_M, B_H be disjoint operational probability bands of radius 0.10 around the three catalogue centers. The authorized model class is the union of five rectangles:
AND=B_L×B_L, X=B_L×B_H, INTERACTION=B_M×B_M, Z=B_H×B_L, OR=B_H×B_H.

For each intervention a and Bernoulli sequence with S_n successes and F_n failures, use the Jeffreys predictive distribution
Q(y_1:n)=B(S_n+1/2,F_n+1/2)/B(1/2,1/2).
For every fixed p, E_n(p)=Q/P_p is a nonnegative likelihood-ratio martingale. Thus the inverted confidence sequence C_a,n={p:E_n(p)<1/alpha_a} has time-uniform coverage at level 1-alpha_a.

We use alpha_a=.025 for each of two interventions. By union bound, both coordinate confidence sequences simultaneously cover their true probabilities with probability at least .95.

A coordinate is labelled only when its whole confidence interval lies inside exactly one operational band. A coordinate outside all bands triggers MODEL_CLASS_BREAK. When both labels resolve, legal band products certify a catalogue class and illegal products trigger MODEL_CLASS_BREAK. On the simultaneous-coverage event, a terminal classification cannot be wrong relative to this operational class. The procedure may HOLD when finite data cannot close the distinction.
