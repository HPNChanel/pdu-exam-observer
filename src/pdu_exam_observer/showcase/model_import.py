"""Strict local import and atomic activation for immutable ONNX model bundles."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .model_runtime import ModelRuntime

BUNDLE_FILES = frozenset(
    {
        "model.onnx",
        "manifest.json",
        "calibration.json",
        "policy.json",
        "checksums.json",
        "golden_inputs.npz",
        "golden_outputs.npz",
        "MODEL_CARD.md",
    }
)
MAX_FILE_BYTES = {
    "model.onnx": 64 * 1024 * 1024,
    "manifest.json": 256 * 1024,
    "calibration.json": 256 * 1024,
    "policy.json": 256 * 1024,
    "checksums.json": 256 * 1024,
    "golden_inputs.npz": 16 * 1024 * 1024,
    "golden_outputs.npz": 1024 * 1024,
    "MODEL_CARD.md": 512 * 1024,
}
_MAX_ARCHIVE_BYTES = 80 * 1024 * 1024
_MAX_COMPRESSION_RATIO = 200
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class BundleImportError(ValueError):
    """Raised when a bundle fails the immutable import contract."""


@dataclass(frozen=True, slots=True)
class BundleImportResult:
    status: str
    bundle_sha256: str
    bundle_path: Path


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except OSError:
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _verify_managed_directory(path: Path) -> None:
    if not path.is_dir() or _is_reparse(path):
        raise BundleImportError("model registry directory is not a trusted regular directory")


def _read_bundle(source: bytes | Path) -> bytes:
    if isinstance(source, bytes):
        data = source
    elif isinstance(source, Path):
        if not source.is_file() or source.is_symlink():
            raise BundleImportError("bundle path must be a trusted regular file")
        data = source.read_bytes()
    else:
        raise TypeError("bundle source must be bytes or a trusted native Path")
    if len(data) > _MAX_ARCHIVE_BYTES:
        raise BundleImportError("bundle ZIP exceeds its size ceiling")
    return data


def _verify_archive(archive: zipfile.ZipFile) -> tuple[zipfile.ZipInfo, ...]:
    entries = tuple(archive.infolist())
    if len(entries) != len(BUNDLE_FILES) or {entry.filename for entry in entries} != BUNDLE_FILES:
        raise BundleImportError("bundle archive does not match the exact allowlist")
    for entry in entries:
        unix_mode = (entry.external_attr >> 16) & 0o170000
        if (
            entry.is_dir()
            or entry.filename != Path(entry.filename).name
            or "\\" in entry.filename
            or ":" in entry.filename
            or unix_mode == 0o120000
        ):
            raise BundleImportError("bundle archive contains an unsafe entry")
        if entry.file_size > MAX_FILE_BYTES[entry.filename]:
            raise BundleImportError("bundle archive entry exceeds its size ceiling")
        if entry.file_size and (
            entry.compress_size == 0
            or entry.file_size / entry.compress_size > _MAX_COMPRESSION_RATIO
        ):
            raise BundleImportError("bundle archive compression ratio is unsafe")
    return entries


def _verify_staged_contract(path: Path) -> None:
    _verify_managed_directory(path)
    try:
        children = tuple(path.iterdir())
    except OSError as error:
        raise BundleImportError("bundle directory cannot be inspected") from error
    if {child.name for child in children} != BUNDLE_FILES:
        raise BundleImportError("bundle directory does not match the exact allowlist")
    for child in children:
        try:
            metadata = os.lstat(child)
        except OSError as error:
            raise BundleImportError("bundle file cannot be inspected") from error
        if (
            not child.is_file()
            or _is_reparse(child)
            or metadata.st_nlink != 1
            or metadata.st_size > MAX_FILE_BYTES[child.name]
        ):
            raise BundleImportError("bundle contains an unsafe file")
    try:
        checksums = json.loads((path / "checksums.json").read_text(encoding="utf-8"))
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BundleImportError("bundle JSON contract is invalid") from error
    payload_names = BUNDLE_FILES - {"checksums.json"}
    if (
        not isinstance(checksums, dict)
        or checksums.get("schema_version") != 1
        or checksums.get("algorithm") != "SHA-256"
        or not isinstance(checksums.get("files"), dict)
        or set(checksums["files"]) != payload_names
    ):
        raise BundleImportError("bundle checksums contract is invalid")
    for name in payload_names:
        if checksums["files"].get(name) != _digest_bytes((path / name).read_bytes()):
            raise BundleImportError(f"bundle checksum mismatch for {name}")
    required_manifest = {
        "schema_version": 1,
        "runtime_schema_min": 1,
        "runtime_schema_max": 1,
        "preprocessing_id": "mediapipe33-bodycenter-resample90-v1",
    }
    if not isinstance(manifest, dict) or any(
        manifest.get(key) != value for key, value in required_manifest.items()
    ):
        raise BundleImportError("bundle manifest is incompatible")
    for key in ("model_version", "policy_version"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value or len(value) > 128:
            raise BundleImportError("bundle manifest version is invalid")


def _default_validator(path: Path) -> str:
    from .model_runtime import ModelRuntime

    return ModelRuntime.from_bundle(path).status


class ModelRegistry:
    """Own the only mutable pointer to a fully validated model version."""

    def __init__(
        self,
        model_root: Path,
        *,
        validator: Callable[[Path], str] | None = None,
    ) -> None:
        self.model_root = model_root
        self._uses_default_validator = validator is None
        self._validator = validator or _default_validator
        self._cached_digest: str | None = None
        self._cached_fingerprint: tuple[tuple[str, int, int], ...] | None = None
        self._cached_runtime: ModelRuntime | None = None

    def import_bundle(self, source: bytes | Path) -> BundleImportResult:
        data = _read_bundle(source)
        digest = _digest_bytes(data)
        self.model_root.mkdir(parents=True, exist_ok=True)
        _verify_managed_directory(self.model_root)
        versions = self.model_root / "versions"
        versions.mkdir(exist_ok=True)
        _verify_managed_directory(versions)
        destination = versions / digest
        staging: Path | None = None
        try:
            if not destination.exists():
                staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.model_root))
                with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
                    for entry in _verify_archive(archive):
                        with (
                            archive.open(entry) as source_handle,
                            (staging / entry.filename).open("wb") as destination_handle,
                        ):
                            shutil.copyfileobj(
                                source_handle, destination_handle, length=1024 * 1024
                            )
                _verify_staged_contract(staging)
                status = self._validator(staging)
                if status != "READY":
                    raise BundleImportError(f"bundle runtime validation failed: {status}")
                staging.replace(destination)
                staging = None
            else:
                _verify_staged_contract(destination)
                status = self._validator(destination)
                if status != "READY":
                    raise BundleImportError(f"existing bundle validation failed: {status}")
            pointer = {"schema_version": 1, "bundle_sha256": digest}
            descriptor, partial_name = tempfile.mkstemp(
                prefix="active-", suffix=".partial", dir=self.model_root
            )
            partial = Path(partial_name)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(pointer, sort_keys=True, separators=(",", ":")) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(partial, self.model_root / "active.json")
            finally:
                partial.unlink(missing_ok=True)
            self._cached_digest = None
            self._cached_fingerprint = None
            self._cached_runtime = None
            return BundleImportResult("READY", digest, destination)
        except (zipfile.BadZipFile, OSError, KeyError) as error:
            raise BundleImportError("bundle staging or activation failed") from error
        finally:
            if staging is not None and staging.is_dir():
                shutil.rmtree(staging)

    def active_bundle(self) -> Path | None:
        try:
            pointer = json.loads((self.model_root / "active.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(pointer, dict):
            return None
        digest = pointer.get("bundle_sha256")
        if (
            pointer.get("schema_version") != 1
            or not isinstance(digest, str)
            or not _DIGEST.fullmatch(digest)
        ):
            return None
        candidate = self.model_root / "versions" / digest
        if not candidate.is_dir() or _is_reparse(candidate):
            return None
        try:
            if {item.name for item in candidate.iterdir()} != BUNDLE_FILES:
                return None
        except OSError:
            return None
        return candidate

    def status(self) -> dict[str, object]:
        active = self.active_bundle()
        if active is None:
            return {"status": "MODEL_UNAVAILABLE", "bundle_sha256": None}
        try:
            _verify_staged_contract(active)
            runtime = self._runtime_for_active(active) if self._uses_default_validator else None
            validation_status = runtime.status if runtime is not None else self._validator(active)
            if validation_status != "READY":
                return {"status": validation_status, "bundle_sha256": active.name}
            manifest = json.loads((active / "manifest.json").read_text(encoding="utf-8"))
        except (BundleImportError, OSError, UnicodeError, json.JSONDecodeError, KeyError):
            return {"status": "MODEL_INTEGRITY_FAILED", "bundle_sha256": active.name}
        return {
            "status": "READY",
            "bundle_sha256": active.name,
            "model_version": manifest["model_version"],
            "policy_version": manifest["policy_version"],
            "preprocessing_id": manifest["preprocessing_id"],
        }

    def import_bytes(self, payload: bytes) -> dict[str, object]:
        """Workspace-service facade: import native bytes and return public status."""

        self.import_bundle(payload)
        return self.status()

    @staticmethod
    def _fingerprint(path: Path) -> tuple[tuple[str, int, int], ...]:
        return tuple(
            sorted(
                (child.name, child.stat().st_size, child.stat().st_mtime_ns)
                for child in path.iterdir()
            )
        )

    def _runtime_for_active(self, active: Path) -> ModelRuntime:
        fingerprint = self._fingerprint(active)
        if (
            self._cached_digest == active.name
            and self._cached_fingerprint == fingerprint
            and self._cached_runtime is not None
        ):
            return self._cached_runtime
        _verify_staged_contract(active)
        from .model_runtime import ModelRuntime

        runtime = ModelRuntime.from_bundle(active)
        if runtime.status == "READY":
            self._cached_digest = active.name
            self._cached_fingerprint = fingerprint
            self._cached_runtime = runtime
        else:
            self._cached_digest = None
            self._cached_fingerprint = None
            self._cached_runtime = None
        return runtime

    def infer_pose_tensor(
        self,
        pose_tensor: Any,
        context: Mapping[str, float] | None = None,
        *,
        source_kind: str = "REAL",
    ) -> Mapping[str, object] | None:
        active = self.active_bundle()
        if active is None:
            return None
        try:
            runtime = self._runtime_for_active(active)
        except (BundleImportError, OSError, ValueError):
            return None
        return runtime.infer_pose_tensor(
            pose_tensor,
            context=context,
            source_kind=source_kind,
        )

    def model_provider(self, packet: Mapping[str, object]) -> Mapping[str, object] | None:
        """Runtime seam for one preprocessed temporal tensor and its bounded context."""

        tensor = packet.get("pose_tensor")
        context = packet.get("context")
        source_kind = packet.get("source_kind")
        if tensor is None or not isinstance(context, Mapping) or not isinstance(source_kind, str):
            return None
        normalized_context: dict[str, float] = {}
        for key, value in context.items():
            if (
                not isinstance(key, str)
                or isinstance(value, bool)
                or not isinstance(value, int | float)
            ):
                return None
            normalized_context[key] = float(value)
        return self.infer_pose_tensor(
            tensor,
            normalized_context,
            source_kind=source_kind,
        )
