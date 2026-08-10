from __future__ import annotations

import sqlite3

import transport_guard_base as _base


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


_original_connect = sqlite3.connect


def _closing_connect(*args, **kwargs):
    kwargs.setdefault("factory", _ClosingConnection)
    return _original_connect(*args, **kwargs)


_base.sqlite3.connect = _closing_connect

TransportError = _base.TransportError
TransportGuard = _base.TransportGuard
canonical = _base.canonical
sha = _base.sha

__all__ = ["TransportError", "TransportGuard", "canonical", "sha"]
