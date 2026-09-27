"""Independent PyMC realization of the ΠG-006 posterior regret field."""
from __future__ import annotations

import numpy as np

BACKEND_FAMILY = "PyMC"
FIELD_SEMANTICS = "StudentT4 model-indexed regression with sum-zero subject effects"


def build_regret_field(data: dict[str, np.ndarray]):
    import pymc as pm
    import pytensor.tensor as pt
    z = np.asarray(data["z"], dtype=float)
    x = np.asarray(data["X"], dtype=float)
    model_idx = np.asarray(data["model_idx"], dtype="int32")
    subject_idx = np.asarray(data["subject_idx"], dtype="int32")
    basis = np.asarray(data["basis"], dtype=float)
    m = int(data["n_models"])
    k = x.shape[1]
    j = basis.shape[0]
    with pm.Model() as model:
        alpha = pm.Normal("alpha", mu=0.0, sigma=1.5, shape=m)
        beta = pm.Normal("beta", mu=0.0, sigma=0.35, shape=(m, k))
        sigma = pm.HalfNormal("sigma", sigma=0.75, shape=m)
        tau_subject = pm.HalfNormal("tau_subject", sigma=0.50, shape=m)
        u_subject = pm.Normal("u_subject", mu=0.0, sigma=1.0, shape=(m, j - 1))
        subject_effect = pm.Deterministic("subject_effect", tau_subject[:, None] * pt.dot(u_subject, pt.as_tensor_variable(basis.T)))
        mu = alpha[model_idx] + pt.sum(beta[model_idx] * x, axis=1) + subject_effect[model_idx, subject_idx]
        pm.StudentT("obs", nu=4.0, mu=mu, sigma=sigma[model_idx], observed=z)
    return model
