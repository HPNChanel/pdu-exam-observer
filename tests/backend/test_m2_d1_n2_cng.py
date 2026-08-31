from __future__ import annotations

import ctypes
import hashlib
from typing import Any

from pdu_exam_observer.m2_d1_n2_cng import verify_ecdsa_p256_sha256_p1363


def _ephemeral_test_vector(message: bytes) -> tuple[bytes, bytes]:
    bcrypt: Any = ctypes.WinDLL("bcrypt", use_last_error=True)
    algorithm = ctypes.c_void_p()
    key = ctypes.c_void_p()
    bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_ulong,
    ]
    bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long
    bcrypt.BCryptGenerateKeyPair.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    bcrypt.BCryptGenerateKeyPair.restype = ctypes.c_long
    bcrypt.BCryptFinalizeKeyPair.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    bcrypt.BCryptFinalizeKeyPair.restype = ctypes.c_long
    bcrypt.BCryptExportKey.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_ulong,
    ]
    bcrypt.BCryptExportKey.restype = ctypes.c_long
    bcrypt.BCryptSignHash.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_ulong,
    ]
    bcrypt.BCryptSignHash.restype = ctypes.c_long
    bcrypt.BCryptDestroyKey.argtypes = [ctypes.c_void_p]
    bcrypt.BCryptDestroyKey.restype = ctypes.c_long
    bcrypt.BCryptCloseAlgorithmProvider.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    bcrypt.BCryptCloseAlgorithmProvider.restype = ctypes.c_long
    try:
        assert bcrypt.BCryptOpenAlgorithmProvider(
            ctypes.byref(algorithm), "ECDSA_P256", None, 0
        ) == 0
        assert bcrypt.BCryptGenerateKeyPair(
            algorithm, ctypes.byref(key), 256, 0
        ) == 0
        assert bcrypt.BCryptFinalizeKeyPair(key, 0) == 0
        public_size = ctypes.c_ulong()
        assert bcrypt.BCryptExportKey(
            key, None, "ECCPUBLICBLOB", None, 0, ctypes.byref(public_size), 0
        ) == 0
        public_buffer = (ctypes.c_ubyte * public_size.value)()
        assert bcrypt.BCryptExportKey(
            key,
            None,
            "ECCPUBLICBLOB",
            public_buffer,
            len(public_buffer),
            ctypes.byref(public_size),
            0,
        ) == 0
        digest = hashlib.sha256(message).digest()
        digest_buffer = (ctypes.c_ubyte * len(digest)).from_buffer_copy(digest)
        signature_size = ctypes.c_ulong()
        assert bcrypt.BCryptSignHash(
            key,
            None,
            digest_buffer,
            len(digest_buffer),
            None,
            0,
            ctypes.byref(signature_size),
            0,
        ) == 0
        signature_buffer = (ctypes.c_ubyte * signature_size.value)()
        assert bcrypt.BCryptSignHash(
            key,
            None,
            digest_buffer,
            len(digest_buffer),
            signature_buffer,
            len(signature_buffer),
            ctypes.byref(signature_size),
            0,
        ) == 0
        return bytes(public_buffer), bytes(signature_buffer)
    finally:
        if key.value:
            assert bcrypt.BCryptDestroyKey(key) == 0
        if algorithm.value:
            assert bcrypt.BCryptCloseAlgorithmProvider(algorithm, 0) == 0


def test_real_bcrypt_verifier_accepts_p256_sha256_p1363_and_rejects_mutation() -> None:
    message = b"canonical-bootstrap-body"
    public_blob, signature = _ephemeral_test_vector(message)

    assert verify_ecdsa_p256_sha256_p1363(public_blob, message, signature)
    assert not verify_ecdsa_p256_sha256_p1363(public_blob, message + b"!", signature)
    assert not verify_ecdsa_p256_sha256_p1363(
        public_blob, message, signature[:-1] + bytes([signature[-1] ^ 1])
    )
    assert not verify_ecdsa_p256_sha256_p1363(public_blob, message, signature[:-1])
