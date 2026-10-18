#!/usr/bin/env python3
"""Data-layout adapter for the frozen v0.12 collector.

The initial collector expected source JSON under data/<lang>.json, but the
resolved facebook/belebele revision exposes auto-converted parquet at
<lang>/test/0000.parquet. This adapter changes data loading only.
"""
from __future__ import annotations

import pandas as pd

import falcon_belebele_collect as base

_original_download = base.hf_hub_download


def redirected_download(*args, **kwargs):
    filename = kwargs.get("filename")
    if filename == f"data/{base.LANG}.json":
        kwargs["filename"] = f"{base.LANG}/test/0000.parquet"
    return _original_download(*args, **kwargs)


def parquet_records(path: str):
    return pd.read_parquet(path).to_dict("records")


base.hf_hub_download = redirected_download
base.load_json_records = parquet_records
base.main()
