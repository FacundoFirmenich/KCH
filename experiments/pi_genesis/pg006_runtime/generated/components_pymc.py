"""Independent PyMC realization of the frozen ΠG-006 component IR."""
from __future__ import annotations

from typing import Any
import numpy as np

IR_SHA256 = "280403a5fbdc1f8817218a4ac8f5d5b0d8e530934834c0cc3b400881d53f0f8a"
BACKEND_FAMILY = "PyMC"
MODELS = ("P0_POPULATION", "P1_GLOBAL_POOL", "P2_GLOBAL_LOCAL", "P3_LOW_POOL")


def build_component(data: dict[str, Any], model_id: str):
    import pymc as pm
    import pytensor.tensor as pt
    if model_id not in MODELS:
        raise ValueError(model_id)
    y = np.asarray(data["y"], dtype=float)
    t = np.asarray(data["t"], dtype=float)
    group = np.asarray(data["group"], dtype="int32")
    basis = np.asarray(data["basis"], dtype=float)
    projector = np.asarray(data["projector"], dtype=float)
    j = basis.shape[0]
    with pm.Model() as model:
        alpha = pm.Normal("alpha", mu=0.0, sigma=1.0)
        beta = pm.Normal("beta", mu=0.0, sigma=1.0)
        sigma = pm.HalfNormal("sigma", sigma=1.0)
        zero = pt.zeros(j)
        a = zero
        b = zero
        if model_id == "P1_GLOBAL_POOL":
            tau_a = pm.HalfNormal("tau_a", sigma=0.75)
            tau_b = pm.HalfNormal("tau_b", sigma=0.50)
            u_a = pm.Normal("u_a", mu=0.0, sigma=1.0, shape=j - 1)
            u_b = pm.Normal("u_b", mu=0.0, sigma=1.0, shape=j - 1)
            a = pm.Deterministic("a", tau_a * pt.dot(pt.as_tensor_variable(basis), u_a))
            b = pm.Deterministic("b", tau_b * pt.dot(pt.as_tensor_variable(basis), u_b))
        elif model_id == "P2_GLOBAL_LOCAL":
            tau_a = pm.HalfNormal("tau_a", sigma=0.25)
            tau_b = pm.HalfNormal("tau_b", sigma=0.20)
            lambda_a = pm.HalfStudentT("lambda_a", nu=3.0, sigma=1.0, shape=j)
            lambda_b = pm.HalfStudentT("lambda_b", nu=3.0, sigma=1.0, shape=j)
            u_a = pm.Normal("u_a", mu=0.0, sigma=1.0, shape=j - 1)
            u_b = pm.Normal("u_b", mu=0.0, sigma=1.0, shape=j - 1)
            w_a = pt.dot(pt.as_tensor_variable(basis), u_a)
            w_b = pt.dot(pt.as_tensor_variable(basis), u_b)
            lt_a = pt.sqrt((lambda_a**2) / (1.0 + tau_a**2 * lambda_a**2))
            lt_b = pt.sqrt((0.75**2 * lambda_b**2) / (0.75**2 + tau_b**2 * lambda_b**2))
            s_a = pm.Deterministic("s_a", tau_a * lt_a)
            s_b = pm.Deterministic("s_b", tau_b * lt_b)
            a = pm.Deterministic("a", pt.dot(pt.as_tensor_variable(projector), s_a * w_a))
            b = pm.Deterministic("b", pt.dot(pt.as_tensor_variable(projector), s_b * w_b))
        elif model_id == "P3_LOW_POOL":
            u_a = pm.Normal("u_a", mu=0.0, sigma=1.0, shape=j - 1)
            u_b = pm.Normal("u_b", mu=0.0, sigma=1.0, shape=j - 1)
            a = pm.Deterministic("a", pt.dot(pt.as_tensor_variable(basis), u_a))
            b = pm.Deterministic("b", 0.60 * pt.dot(pt.as_tensor_variable(basis), u_b))
        mu = alpha + beta * t
        if model_id != "P0_POPULATION":
            mu = mu + a[group] + b[group] * t
        pm.Normal("obs", mu=mu, sigma=sigma, observed=y)
    return model
