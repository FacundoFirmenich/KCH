from __future__ import annotations

from typing import Any

from .ledger_base import SCOConflictError, SCOError, SCOService as _SCOService


class SCOService(_SCOService):
    @staticmethod
    def _projection_insert(connection, table: str, identity: str, record: dict[str, Any], event_hash: str, extra: tuple[Any, ...], columns: str) -> None:
        """Correct column arity for identity + extra projection columns + record triple."""
        from .models import canonical_json
        from .ledger_base import _sha_text

        record_json = canonical_json(record)
        record_hash = _sha_text(record_json)
        placeholders = ",".join("?" for _ in range(4 + len(extra)))
        connection.execute(
            f"INSERT INTO {table}({columns},record_json,record_sha256,event_hash) VALUES({placeholders})",
            (identity, *extra, record_json, record_hash, event_hash),
        )


__all__ = ["SCOService", "SCOError", "SCOConflictError"]
