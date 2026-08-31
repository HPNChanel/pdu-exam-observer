"""Shared transaction seam for one guarded operational SQLite owner.

The protocol is intentionally structural.  Legacy :class:`M1Store` and the
accepted guarded P1 store can both own the sole SQLite connection used by an
``M1Backend``.  It does not create a root, open a database, or grant authority.
"""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol


class StoreLock(Protocol):
    """Minimum lock surface used by the legacy M1 read paths."""

    def __enter__(self) -> object: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> bool | None: ...


class SQLiteStoreOwner(Protocol):
    """One owner, one connection, and one serialized transaction boundary."""

    root: Path
    database_path: Path
    connection: sqlite3.Connection
    schema_version: int
    _lock: StoreLock

    def transaction(self) -> AbstractContextManager[sqlite3.Connection]: ...

    def require_valid_parents(
        self, connection: sqlite3.Connection, parents: tuple[str, ...]
    ) -> None: ...

    def close(self) -> None: ...
