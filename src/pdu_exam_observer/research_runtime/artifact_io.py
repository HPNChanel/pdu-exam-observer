"""Read a regular artifact without following a leaf reparse point."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

from .root_lease import has_reparse_component


def open_regular_read(path: Path) -> BinaryIO:
    if has_reparse_component(path):
        raise ValueError("ARTIFACT_SCOPE_INVALID")
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create.restype = wintypes.HANDLE
        handle = create(str(path), 0x80000000, 1, None, 3, 0x00200000, None)
        if handle == wintypes.HANDLE(-1).value:
            raise OSError("ARTIFACT_OPEN_FAILED")

        class AttributeTag(ctypes.Structure):
            _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

        query = kernel.GetFileInformationByHandleEx
        query.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        query.restype = wintypes.BOOL
        information = AttributeTag()
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        if not query(
            handle, 9, ctypes.byref(information), ctypes.sizeof(information)
        ) or information.attributes & (0x400 | 0x10):
            close(handle)
            raise ValueError("ARTIFACT_SCOPE_INVALID")
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        stream = os.fdopen(descriptor, "rb")
    else:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        stream = os.fdopen(descriptor, "rb")
    metadata = os.fstat(stream.fileno())
    if metadata.st_nlink != 1 or bool(getattr(metadata, "st_file_attributes", 0) & 0x400):
        stream.close()
        raise ValueError("ARTIFACT_SCOPE_INVALID")
    return stream
