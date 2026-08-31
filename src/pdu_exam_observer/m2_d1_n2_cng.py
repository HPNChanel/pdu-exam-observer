"""Public-only BCrypt verifier for the fixed D1-N2 P-256 profile."""

from __future__ import annotations

import ctypes
import hashlib
import os
import struct
from typing import Any

_BCRYPT_ECDSA_PUBLIC_P256_MAGIC = 0x31534345
_PUBLIC_BLOB_BYTES = 72
_P256_COORDINATE_BYTES = 32
_P1363_SIGNATURE_BYTES = 64


class _BCryptApi:
    def __init__(self) -> None:
        self._api: Any = ctypes.WinDLL("bcrypt", use_last_error=True)
        self._api.BCryptOpenAlgorithmProvider.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
        ]
        self._api.BCryptOpenAlgorithmProvider.restype = ctypes.c_long
        self._api.BCryptImportKeyPair.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self._api.BCryptImportKeyPair.restype = ctypes.c_long
        self._api.BCryptVerifySignature.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self._api.BCryptVerifySignature.restype = ctypes.c_long
        self._api.BCryptDestroyKey.argtypes = [ctypes.c_void_p]
        self._api.BCryptDestroyKey.restype = ctypes.c_long
        self._api.BCryptCloseAlgorithmProvider.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self._api.BCryptCloseAlgorithmProvider.restype = ctypes.c_long

    def verify(self, public_blob: bytes, digest: bytes, signature: bytes) -> bool:
        algorithm = ctypes.c_void_p()
        key = ctypes.c_void_p()
        clean = True
        verified = False
        try:
            opened = self._api.BCryptOpenAlgorithmProvider(
                ctypes.byref(algorithm), "ECDSA_P256", None, 0
            )
            if opened == 0:
                public_buffer = (ctypes.c_ubyte * len(public_blob)).from_buffer_copy(
                    public_blob
                )
                imported = self._api.BCryptImportKeyPair(
                    algorithm,
                    None,
                    "ECCPUBLICBLOB",
                    ctypes.byref(key),
                    public_buffer,
                    len(public_buffer),
                    0,
                )
                if imported == 0:
                    digest_buffer = (ctypes.c_ubyte * len(digest)).from_buffer_copy(
                        digest
                    )
                    signature_buffer = (
                        ctypes.c_ubyte * len(signature)
                    ).from_buffer_copy(signature)
                    verified = bool(
                        self._api.BCryptVerifySignature(
                            key,
                            None,
                            digest_buffer,
                            len(digest_buffer),
                            signature_buffer,
                            len(signature_buffer),
                            0,
                        )
                        == 0
                    )
        except BaseException:
            verified = False
        finally:
            if key.value:
                try:
                    clean = self._api.BCryptDestroyKey(key) == 0 and clean
                except BaseException:
                    clean = False
            if algorithm.value:
                try:
                    clean = (
                        self._api.BCryptCloseAlgorithmProvider(algorithm, 0) == 0
                        and clean
                    )
                except BaseException:
                    clean = False
        return bool(verified and clean)


def _valid_public_blob(value: object) -> bool:
    if type(value) is not bytes or len(value) != _PUBLIC_BLOB_BYTES:
        return False
    magic, coordinate_size = struct.unpack("<II", value[:8])
    return bool(
        magic == _BCRYPT_ECDSA_PUBLIC_P256_MAGIC
        and coordinate_size == _P256_COORDINATE_BYTES
    )


def verify_ecdsa_p256_sha256_p1363(
    public_blob: bytes,
    message: bytes,
    signature: bytes,
) -> bool:
    """Verify the sole allowed signature profile without retaining key state."""

    if (
        os.name != "nt"
        or not _valid_public_blob(public_blob)
        or type(message) is not bytes
        or type(signature) is not bytes
        or len(signature) != _P1363_SIGNATURE_BYTES
    ):
        return False
    return _BCryptApi().verify(public_blob, hashlib.sha256(message).digest(), signature)


__all__ = ["verify_ecdsa_p256_sha256_p1363"]
