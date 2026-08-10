from __future__ import annotations

import sqlite3

from .ledger import KwanPromptsLedger as _KwanPromptsLedger


class _AutoClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class KwanPromptsLedger(_KwanPromptsLedger):
    """Windows-safe ledger connection lifecycle.

    sqlite3.Connection's standard context manager commits or rolls back but
    does not close.  This factory closes deterministically after every scoped
    operation, preventing locked state files in long-running KCH processes.
    """

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, factory=_AutoClosingConnection)
        connection.row_factory = sqlite3.Row
        return connection

