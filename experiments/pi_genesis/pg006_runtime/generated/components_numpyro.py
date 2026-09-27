"""Independent NumPyro realization of the frozen ΠG-006 component IR."""
from __future__ import annotations

import jax.numpy as jnp
import numpyro
import numpyro.distributions as dist

IR_SHA256 = "280403a5fbdc1f8817218a4ac8f5d5b0d8e530934834c0cc3b400881d53f0f8a"
BACKEND_FAMILY = "NumPyro"
MODELS = ("P0_POPULATION", "P1_GLOBAL_POOL", "P2_GLOBAL_LOCAL", "P3_LOW_POOL")


def half_student_t(df: float, scale: float = 1.0):
    """Exact folded Student-t realization of a centered half-Student prior."""
    return dist.FoldedDistribution(dist.StudentT(df, loc=0.0, scale=scale))


def component_model(y, t, group, basis, projector, model_id: str):
    if model_id not in MODELS:
        raise ValueError(model_id)
    j = basis.shape[0]
    alpha = numpyro.sample("alpha", dist.Normal(0.0, 1.0))
    beta = numpyro.sample("beta", dist.Normal(0.0, 1.0))
    sigma = numpyro.sample("sigma", dist.HalfNormal(1.0))
    a = jnp.zeros((j,))
    b = jnp.zeros((j,))
    if model_id == "P1_GLOBAL_POOL":
        tau_a = numpyro.sample("tau_a", dist.HalfNormal(0.75))
        tau_b = numpyro.sample("tau_b", dist.HalfNormal(0.50))
        u_a = numpyro.sample("u_a", dist.Normal(0.0, 1.0).expand((j - 1,)).to_event(1))
        u_b = numpyro.sample("u_b", dist.Normal(0.0, 1.0).expand((j - 1,)).to_event(1))
        a = tau_a * (basis @ u_a)
        b = tau_b * (basis @ u_b)
    elif model_id == "P2_GLOBAL_LOCAL":
        tau_a = numpyro.sample("tau_a", dist.HalfNormal(0.25))
        tau_b = numpyro.sample("tau_b", dist.HalfNormal(0.20))
        lambda_a = numpyro.sample("lambda_a", half_student_t(3.0, 1.0).expand((j,)).to_event(1))
        lambda_b = numpyro.sample("lambda_b", half_student_t(3.0, 1.0).expand((j,)).to_event(1))
        u_a = numpyro.sample("u_a", dist.Normal(0.0, 1.0).expand((j - 1,)).to_event(1))
        u_b = numpyro.sample("u_b", dist.Normal(0.0, 1.0).expand((j - 1,)).to_event(1))
        w_a = basis @ u_a
        w_b = basis @ u_b
        lt_a = jnp.sqrt((lambda_a**2) / (1.0 + tau_a**2 * lambda_a**2))
        lt_b = jnp.sqrt((0.75**2 * lambda_b**2) / (0.75**2 + tau_b**2 * lambda_b**2))
        s_a = tau_a * lt_a
        s_b = tau_b * lt_b
        numpyro.deterministic("s_a", s_a)
        numpyro.deterministic("s_b", s_b)
        a = projector @ (s_a * w_a)
        b = projector @ (s_b * w_b)
    elif model_id == "P3_LOW_POOL":
        u_a = numpyro.sample("u_a", dist.Normal(0.0, 1.0).expand((j - 1,)).to_event(1))
        u_b = numpyro.sample("u_b", dist.Normal(0.0, 1.0).expand((j - 1,)).to_event(1))
        a = basis @ u_a
        b = 0.60 * (basis @ u_b)
    if model_id != "P0_POPULATION":
        numpyro.deterministic("a", a)
        numpyro.deterministic("b", b)
    mu = alpha + beta * t
    if model_id != "P0_POPULATION":
        mu = mu + a[group] + b[group] * t
    numpyro.sample("obs", dist.Normal(mu, sigma), obs=y)
