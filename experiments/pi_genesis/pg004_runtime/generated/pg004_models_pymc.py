"""PyMC realization of the frozen PG004 Statistical IR.

This module intentionally implements its own probability program. It does not
import a shared generated likelihood kernel from the NumPyro realization.
"""
from __future__ import annotations

from typing import Any
import numpy as np

IR_SHA256 = "105dc2449fd7bdc7836e88b302d6db49892b9147a4a217b59f4f378661875397"
BACKEND_FAMILY = "PyMC"


def build_grunfeld(data: Any, encoding: str):
    import pymc as pm
    import pytensor.tensor as pt
    y = np.asarray(data["y"], dtype=float)
    x_value = np.asarray(data["x_value"], dtype=float)
    x_capital = np.asarray(data["x_capital"], dtype=float)
    group = np.asarray(data["group"], dtype="int32")
    basis = np.asarray(data["basis"], dtype=float)
    n_groups = int(basis.shape[0])
    with pm.Model() as model:
        alpha = pm.Normal("alpha", mu=0.0, sigma=1.0)
        beta_value = pm.Normal("beta_value", mu=0.0, sigma=1.0)
        beta_capital = pm.Normal("beta_capital", mu=0.0, sigma=1.0)
        tau_alpha = pm.HalfNormal("tau_alpha", sigma=0.5)
        sigma = pm.HalfNormal("sigma", sigma=1.0)
        if encoding == "centered_J":
            z = pm.Normal("z", mu=0.0, sigma=1.0, shape=n_groups)
            a = pm.Deterministic("a", tau_alpha * (z - pt.mean(z)))
        elif encoding == "orthonormal_Jminus1":
            u = pm.Normal("u", mu=0.0, sigma=1.0, shape=n_groups - 1)
            a = pm.Deterministic("a", tau_alpha * pt.dot(pt.as_tensor_variable(basis), u))
        else:
            raise ValueError(encoding)
        mu = alpha + a[group] + beta_value * x_value + beta_capital * x_capital
        pm.StudentT("obs", nu=4.0, mu=mu, sigma=sigma, observed=y)
    return model


def build_baseball(data: Any, encoding: str):
    import pymc as pm
    import pytensor.tensor as pt
    at_bats = np.asarray(data["at_bats"], dtype="int32")
    hits = np.asarray(data["hits"], dtype="int32")
    basis = np.asarray(data["basis"], dtype=float)
    n_groups = int(basis.shape[0])
    with pm.Model() as model:
        alpha = pm.Normal("alpha", mu=-1.0201406732266145, sigma=1.0)
        tau_player = pm.HalfNormal("tau_player", sigma=1.0)
        if encoding == "centered_J":
            z = pm.Normal("z", mu=0.0, sigma=1.0, shape=n_groups)
            a = pm.Deterministic("a", tau_player * (z - pt.mean(z)))
        elif encoding == "orthonormal_Jminus1":
            u = pm.Normal("u", mu=0.0, sigma=1.0, shape=n_groups - 1)
            a = pm.Deterministic("a", tau_player * pt.dot(pt.as_tensor_variable(basis), u))
        else:
            raise ValueError(encoding)
        theta = pm.Deterministic("theta", pm.math.sigmoid(alpha + a))
        pm.Binomial("obs", n=at_bats, p=theta, observed=hits)
    return model
