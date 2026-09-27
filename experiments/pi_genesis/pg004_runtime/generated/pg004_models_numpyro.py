"""NumPyro realization of the frozen PG004 Statistical IR.

This module intentionally implements its own probability program. It does not
import a shared generated likelihood kernel from the PyMC realization.
"""
from __future__ import annotations

import jax.numpy as jnp
import numpyro
import numpyro.distributions as dist

IR_SHA256 = "105dc2449fd7bdc7836e88b302d6db49892b9147a4a217b59f4f378661875397"
BACKEND_FAMILY = "NumPyro"


def grunfeld_model(y, x_value, x_capital, group, basis, encoding: str):
    n_groups = basis.shape[0]
    alpha = numpyro.sample("alpha", dist.Normal(0.0, 1.0))
    beta_value = numpyro.sample("beta_value", dist.Normal(0.0, 1.0))
    beta_capital = numpyro.sample("beta_capital", dist.Normal(0.0, 1.0))
    tau_alpha = numpyro.sample("tau_alpha", dist.HalfNormal(0.5))
    sigma = numpyro.sample("sigma", dist.HalfNormal(1.0))
    if encoding == "centered_J":
        z = numpyro.sample("z", dist.Normal(0.0, 1.0).expand((n_groups,)).to_event(1))
        a = tau_alpha * (z - jnp.mean(z))
    elif encoding == "orthonormal_Jminus1":
        u = numpyro.sample("u", dist.Normal(0.0, 1.0).expand((n_groups - 1,)).to_event(1))
        a = tau_alpha * (basis @ u)
    else:
        raise ValueError(encoding)
    numpyro.deterministic("a", a)
    mu = alpha + a[group] + beta_value * x_value + beta_capital * x_capital
    numpyro.sample("obs", dist.StudentT(df=4.0, loc=mu, scale=sigma), obs=y)


def baseball_model(at_bats, hits, basis, encoding: str):
    n_groups = basis.shape[0]
    alpha = numpyro.sample("alpha", dist.Normal(-1.0201406732266145, 1.0))
    tau_player = numpyro.sample("tau_player", dist.HalfNormal(1.0))
    if encoding == "centered_J":
        z = numpyro.sample("z", dist.Normal(0.0, 1.0).expand((n_groups,)).to_event(1))
        a = tau_player * (z - jnp.mean(z))
    elif encoding == "orthonormal_Jminus1":
        u = numpyro.sample("u", dist.Normal(0.0, 1.0).expand((n_groups - 1,)).to_event(1))
        a = tau_player * (basis @ u)
    else:
        raise ValueError(encoding)
    numpyro.deterministic("a", a)
    theta = 1.0 / (1.0 + jnp.exp(-(alpha + a)))
    numpyro.deterministic("theta", theta)
    numpyro.sample("obs", dist.Binomial(total_count=at_bats, probs=theta), obs=hits)
