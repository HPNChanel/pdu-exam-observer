"""Native-only, fail-closed M1 storage-root configuration."""
# ruff: noqa: E501

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

VerificationStatus = Literal["VERIFIED", "UNKNOWN"]


class ConfigurationError(ValueError):
    """The native configuration or selected root is unsafe."""


@dataclass(frozen=True)
class NativeConfig:
    root: Path
    encryption_status: VerificationStatus
    acl_status: VerificationStatus


def default_config_path() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        raise ConfigurationError("LOCALAPPDATA is required for native configuration")
    return Path(local_app_data) / "PDUExamObserver" / "config.v1.json"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _forbidden_roots() -> tuple[Path, ...]:
    project_root = Path(__file__).resolve().parents[2]
    bundle = Path(getattr(sys, "_MEIPASS", project_root))
    return (
        bundle.resolve(),
        (project_root / "apps" / "web").resolve(),
        (project_root / "_archive").resolve(),
    )


def _has_reparse_component(root: Path) -> bool:
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ConfigurationError("unable to inspect research root for reparse points") from exc
        attributes = getattr(metadata, "st_file_attributes", None)
        if attributes is None:
            if os.name == "nt":
                raise ConfigurationError("unable to inspect research root for reparse points")
            attributes = 0
        if bool(attributes & 0x400):
            return True
    return False


def _check_ntfs(root: Path) -> None:
    if os.name != "nt":
        return
    if not root.drive:
        raise ConfigurationError("research root must include a local Windows drive")
    try:
        import ctypes

        fs_name = ctypes.create_unicode_buffer(261)
        result = ctypes.windll.kernel32.GetVolumeInformationW(
            root.drive + "\\", None, 0, None, None, None, fs_name, len(fs_name)
        )
        if not result:
            raise ConfigurationError("unable to inspect NTFS filesystem for research root")
        if fs_name.value.upper() != "NTFS":
            raise ConfigurationError("research root must be on NTFS")
    except ConfigurationError:
        raise
    except Exception as exc:
        raise ConfigurationError("unable to inspect NTFS filesystem for research root") from exc


def _status(value: object) -> VerificationStatus:
    if value not in {"VERIFIED", "UNKNOWN"}:
        raise ConfigurationError("verification status must be VERIFIED or UNKNOWN")
    return value  # type: ignore[return-value]


# Well-known SIDs that represent "any local user" rather than the owner,
# SYSTEM, or Administrators. An allow-ACE on a broad SID means the storage
# root's confidentiality/integrity cannot be called restrictive.
_BROAD_SIDS = frozenset(
    {
        "S-1-1-0",  # Everyone
        "S-1-5-2",  # Network
        "S-1-5-3",  # Batch
        "S-1-5-4",  # Interactive
        "S-1-5-7",  # Anonymous Logon
        "S-1-5-11",  # Authenticated Users
        "S-1-5-32-545",  # BUILTIN\Users
        "S-1-5-32-546",  # BUILTIN\Guests
    }
)


def _probe_acl(root: Path) -> VerificationStatus:
    """VERIFIED iff the root DACL grants nothing to broad local-user SIDs.

    Standard-user safe (GetNamedSecurityInfoW needs no elevation for an
    owner-readable DACL). Any unreadable or ambiguous result is UNKNOWN;
    DENY ACEs are ignored, which only ever biases toward UNKNOWN.
    """
    import ctypes
    from ctypes import wintypes

    class _AclSizeInformation(ctypes.Structure):
        _fields_ = [
            ("AceCount", wintypes.DWORD),
            ("AclBytesInUse", wintypes.DWORD),
            ("AclBytesFree", wintypes.DWORD),
        ]

    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32
    descriptor = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    status = advapi32.GetNamedSecurityInfoW(
        str(root), 1, 0x0004, None, None, ctypes.byref(dacl), None, ctypes.byref(descriptor)
    )
    if status != 0 or not descriptor:
        return "UNKNOWN"
    try:
        if not dacl:
            return "UNKNOWN"  # NULL DACL: unrestricted
        info = _AclSizeInformation()
        if not advapi32.GetAclInformation(
            dacl, ctypes.byref(info), ctypes.sizeof(info), 2
        ):
            return "UNKNOWN"
        for index in range(info.AceCount):
            ace = ctypes.c_void_p()
            if not advapi32.GetAce(dacl, index, ctypes.byref(ace)):
                return "UNKNOWN"
            ace_address = ace.value
            if ace_address is None:
                return "UNKNOWN"
            ace_type = ctypes.c_uint8.from_address(ace_address).value
            if ace_type != 0x00:  # ACCESS_ALLOWED_ACE only
                continue
            mask = ctypes.c_uint32.from_address(ace_address + 4).value
            sid_out = ctypes.c_void_p()
            if not advapi32.ConvertSidToStringSidW(
                ctypes.c_void_p(ace_address + 8), ctypes.byref(sid_out)
            ):
                return "UNKNOWN"
            try:
                sid_address = sid_out.value
                if sid_address is None:
                    return "UNKNOWN"
                sid = ctypes.wstring_at(sid_address)
            finally:
                kernel32.LocalFree(sid_out)
            if sid in _BROAD_SIDS and mask != 0:
                return "UNKNOWN"
        return "VERIFIED"
    finally:
        kernel32.LocalFree(descriptor)


def _probe_encryption(root: Path) -> VerificationStatus:
    """VERIFIED iff EFS encryption is observed on the root (inherited by
    children). Volume-level BitLocker is not determinable as a standard
    user, so absence of the flag is honestly UNKNOWN, never a denial."""
    attributes = getattr(root.stat(), "st_file_attributes", None)
    if attributes is not None and bool(attributes & 0x4000):
        return "VERIFIED"
    return "UNKNOWN"


def probe_storage_controls(root: Path) -> dict[str, VerificationStatus]:
    """Best-effort, standard-user, offline probe of storage controls.

    `VERIFIED` is emitted only for directly observed evidence; every error,
    non-Windows platform, or undeterminable condition degrades to
    `UNKNOWN`. Never raises.
    """
    result: dict[str, VerificationStatus] = {
        "encryption_status": "UNKNOWN",
        "acl_status": "UNKNOWN",
    }
    if os.name != "nt":
        return result
    try:
        resolved = Path(root).resolve()
        if not resolved.is_dir():
            return result
        result["encryption_status"] = _probe_encryption(resolved)
        result["acl_status"] = _probe_acl(resolved)
    except Exception:
        return {"encryption_status": "UNKNOWN", "acl_status": "UNKNOWN"}
    return result


def validate_storage_root(
    root: Path,
    *,
    create: bool,
    forbidden_roots: tuple[Path, ...] | None = None,
    require_writable: bool = True,
) -> Path:
    if not root.is_absolute():
        raise ConfigurationError("research root must be absolute")
    if os.name == "nt" and str(root).startswith("\\\\"):
        raise ConfigurationError("research root must be local; UNC roots are not allowed")
    if _has_reparse_component(root):
        raise ConfigurationError("research root may not traverse a reparse point")
    resolved = root.resolve()
    for forbidden in forbidden_roots or _forbidden_roots():
        if _is_within(resolved, forbidden.resolve()):
            raise ConfigurationError(
                "research root must be outside bundle, static, and archive locations"
            )
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    if _has_reparse_component(resolved):
        raise ConfigurationError("research root may not traverse a reparse point")
    try:
        resolved = resolved.resolve(strict=True)
    except OSError as exc:
        raise ConfigurationError("research root is unavailable") from exc
    for forbidden in forbidden_roots or _forbidden_roots():
        if _is_within(resolved, forbidden.resolve()):
            raise ConfigurationError(
                "research root must be outside bundle, static, and archive locations"
            )
    if not resolved.is_dir():
        raise ConfigurationError("research root is unavailable")
    if require_writable:
        probe = resolved / ".pdu-write-probe"
        try:
            probe.write_text("ok", encoding="ascii")
            probe.unlink()
        except OSError as exc:
            raise ConfigurationError("research root must be writable") from exc
    _check_ntfs(resolved)
    return resolved


def configure_storage_root(
    root: Path,
    *,
    config_path: Path | None = None,
    encryption_status: str = "UNKNOWN",
    acl_status: str = "UNKNOWN",
    forbidden_roots: tuple[Path, ...] | None = None,
) -> NativeConfig:
    config = NativeConfig(
        validate_storage_root(root, create=True, forbidden_roots=forbidden_roots),
        _status(encryption_status),
        _status(acl_status),
    )
    destination = config_path or default_config_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "root": str(config.root),
                "encryption_status": config.encryption_status,
                "acl_status": config.acl_status,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return config


def load_native_config(
    *, config_path: Path | None = None, require_writable: bool = True
) -> NativeConfig:
    source = config_path or default_config_path()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError("native configuration is unavailable or malformed") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema_version") != 1
        or not isinstance(raw.get("root"), str)
    ):
        raise ConfigurationError("native configuration is malformed")
    return NativeConfig(
        validate_storage_root(
            Path(raw["root"]), create=False, require_writable=require_writable
        ),
        _status(raw.get("encryption_status")),
        _status(raw.get("acl_status")),
    )


def configure_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m pdu_exam_observer configure")
    parser.add_argument("--root", required=True)
    parser.add_argument("--encryption-status", default="UNKNOWN")
    parser.add_argument("--acl-status", default="UNKNOWN")
    arguments = parser.parse_args(argv)
    configure_storage_root(
        Path(arguments.root),
        encryption_status=arguments.encryption_status,
        acl_status=arguments.acl_status,
    )
    print("Configured M1 research storage root.")
