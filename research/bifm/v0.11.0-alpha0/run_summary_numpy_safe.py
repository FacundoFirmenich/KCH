#!/usr/bin/env python3
"""Execute the frozen v0.11 summarizer with NumPy-safe JSON serialization.

This adapter changes serialization only. It does not alter inputs, exact
collision logic, posterior computations, random seed, thresholds or outputs.
"""
from __future__ import annotations
import importlib.util
import json as std_json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
TARGET=HERE/"summarize_bayesian_multisample.py"


def json_default(obj):
    if isinstance(obj,np.generic):
        return obj.item()
    if isinstance(obj,np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class JsonProxy:
    load=staticmethod(std_json.load)
    loads=staticmethod(std_json.loads)
    dump=staticmethod(std_json.dump)
    @staticmethod
    def dumps(obj,*args,**kwargs):
        kwargs.setdefault("default",json_default)
        return std_json.dumps(obj,*args,**kwargs)


spec=importlib.util.spec_from_file_location("bifm_v011_summary",TARGET)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
module.json=JsonProxy
module.main()
