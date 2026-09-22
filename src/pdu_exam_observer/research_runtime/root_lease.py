"""OS-released, non-blocking lease for one runtime owner per storage root."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def has_reparse_component(path: Path) -> bool:
    return any(
        item.is_symlink()
        or (item.exists() and bool(getattr(item.lstat(), "st_file_attributes", 0) & 0x400))
        for item in (path, *path.parents)
    )


class RootLease:
    def __init__(self, root: Path) -> None:
        path = root / "runtime.owner.lock"
        if has_reparse_component(path):
            raise ValueError("UNSAFE_STORAGE_ROOT")
        self.handle: Any = path.open("a+b")
        try:
            self.handle.seek(0, 2)
            if self.handle.tell() == 0:
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import importlib

                fcntl: Any = importlib.import_module("fcntl")
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            raise ValueError("RUNTIME_ROOT_ALREADY_OWNED") from exc

    def close(self) -> None:
        if not self.handle.closed:
            self.handle.close()
