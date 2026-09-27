# Decision-VOI for provenance probes

Let E be the current robust e-value, T the rehabilitation threshold, and D(E)=max(0,log(T/E)).

For probe a with conclusive-result probability q, shadow probability p of SAME_ROOT, and robust outcomes E_S and E_D:

VOI(a)=D(E)-[(1-q)D(E)+q(p D(E_S)+(1-p)D(E_D))].

Net utility is VOI(a)-lambda_c*C(a)-lambda_p*P(a)-lambda_t*L(a), subject to hard authority and privacy-cap constraints. Soft beliefs never modify the hard genealogy. This release implements a one-step/myopic design criterion; it does not claim global optimality over multi-step acquisition.
