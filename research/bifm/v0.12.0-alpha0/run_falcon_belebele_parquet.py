#!/usr/bin/env python3
"""Source-layout adapter for the frozen v0.12 Belebele collector.

The resolved source revision stores each language as data/<lang>.jsonl. This
adapter changes only the filename extension expected by the original collector.
"""
from __future__ import annotations

import falcon_belebele_collect as base

_original_download = base.hf_hub_download


def redirected_download(*args, **kwargs):
    filename = kwargs.get("filename")
    if filename == f"data/{base.LANG}.json":
        kwargs["filename"] = f"data/{base.LANG}.jsonl"
    return _original_download(*args, **kwargs)


base.hf_hub_download = redirected_download
base.main()
