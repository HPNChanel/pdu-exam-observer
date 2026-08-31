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
