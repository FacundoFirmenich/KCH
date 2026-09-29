# G3.7 final closure

G3.7 instantiates DIN as a genuine response-adaptive policy. At H=4, TOS reaches the exact attainable closure frontier (97.9167% closure; 0.0208333 residual bits) while the matched frozen/no-reentry TOS remains at 92.1875% and 0.0768484 bits. The re-entry improvement is +5.7292 percentage points of closure and -0.056015 bits residual entropy; both paired bootstrap intervals exclude zero.

This does **not** establish non-reducibility. Exact dynamic programming reaches the same attainable closure/entropy with 1.67708 expected interventions versus 2.00521 for TOS; cost regret +0.328125, CI95 [+0.20833,+0.46875].

Four of 192 active truth branches remain non-identifiable under the complete admissible intervention class. They remain unresolved rather than being falsely promoted.

GitHub Actions run 36581778154 reproduces truth manifest, policy-result rows, and adjudication byte-for-byte.

Final status: benchmark +0; DIN policy +0 protoform but reducible; canonical DIN not promoted; authority NONE.
