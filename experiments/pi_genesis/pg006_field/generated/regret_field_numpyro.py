"""Independent NumPyro realization of the ΠG-006 posterior regret field."""
from __future__ import annotations

import jax.numpy as jnp
import numpyro
import numpyro.distributions as dist

BACKEND_FAMILY = "NumPyro"
FIELD_SEMANTICS = "StudentT4 model-indexed regression with sum-zero subject effects"


def regret_field_model(z, X, model_idx, subject_idx, basis, n_models: int):
    k = X.shape[1]
    j = basis.shape[0]
    alpha = numpyro.sample("alpha", dist.Normal(0.0, 1.5).expand((n_models,)).to_event(1))
    beta = numpyro.sample("beta", dist.Normal(0.0, 0.35).expand((n_models, k)).to_event(2))
    sigma = numpyro.sample("sigma", dist.HalfNormal(0.75).expand((n_models,)).to_event(1))
    tau_subject = numpyro.sample("tau_subject", dist.HalfNormal(0.50).expand((n_models,)).to_event(1))
    u_subject = numpyro.sample("u_subject", dist.Normal(0.0, 1.0).expand((n_models, j - 1)).to_event(2))
    subject_effect = tau_subject[:, None] * (u_subject @ basis.T)
    numpyro.deterministic("subject_effect", subject_effect)
    mu = alpha[model_idx] + jnp.sum(beta[model_idx] * X, axis=1) + subject_effect[model_idx, subject_idx]
    numpyro.sample("obs", dist.StudentT(df=4.0, loc=mu, scale=sigma[model_idx]), obs=z)
