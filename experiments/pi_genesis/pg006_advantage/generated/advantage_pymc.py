"""PyMC realization of the frozen ΠG-006 mixture-advantage calibrator."""
from __future__ import annotations
import numpy as np
BACKEND_FAMILY="PyMC"
SEMANTICS="StudentT4 calibration of mixture advantage from entropy, regret spread and horizon"

def build_advantage(data: dict[str,np.ndarray]):
 import pymc as pm
 import pytensor.tensor as pt
 y=np.asarray(data['y'],float);X=np.asarray(data['X'],float)
 with pm.Model() as model:
  gamma0=pm.Normal('gamma0',mu=0.,sigma=0.20)
  gamma=pm.Normal('gamma',mu=0.,sigma=0.20,shape=X.shape[1])
  sigma=pm.HalfNormal('sigma',sigma=0.20)
  mu=gamma0+pt.dot(pt.as_tensor_variable(X),gamma)
  pm.StudentT('obs',nu=4.,mu=mu,sigma=sigma,observed=y)
 return model
