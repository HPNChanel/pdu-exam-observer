# PyInstaller one-folder specification for the M2-S3B current-source candidate.
import os
from pathlib import Path

from PyInstaller.building.build_main import COLLECT, EXE, PYZ, Analysis

from pdu_exam_observer.m2_synthetic_environment import BOUND_SOURCE_RELATIVE_PATHS


def required_path(name: str, *, directory: bool = False) -> Path:
    raw = os.environ.get(name)
    if raw is None:
        raise SystemExit(f"{name} is required")
    path = Path(raw)
    if not path.is_absolute():
        raise SystemExit(f"{name} must be absolute")
    if directory and not path.is_dir():
        raise SystemExit(f"{name} must identify a directory")
    if not directory and not path.is_file():
        raise SystemExit(f"{name} must identify a file")
    return path.resolve(strict=True)


project_root = required_path("PDU_PROJECT_ROOT", directory=True)
entry_script = required_path("PDU_ENTRY_SCRIPT")
web_dist = required_path("PDU_WEB_DIST", directory=True)
demo_dir = required_path("PDU_DEMO_DIR", directory=True)
synthetic_binding_files = (
    *BOUND_SOURCE_RELATIVE_PATHS,
    "src/pdu_exam_observer/assets/models/pose_landmarker_lite.task",
)
synthetic_binding_datas = [
    (
        str((project_root / relative).resolve(strict=True)),
        str(Path("synthetic-bindings") / Path(relative).parent),
    )
    for relative in synthetic_binding_files
]

hidden_imports = [
    "fastapi",
    "pdu_exam_observer.api.synthetic_review",
    "pdu_exam_observer.m2_d1_contract",
    "pdu_exam_observer.m2_persistence",
    "pdu_exam_observer.m2_synthetic",
    "pdu_exam_observer.m2_synthetic_environment",
    "pdu_exam_observer.m2_synthetic_evidence",
    "pdu_exam_observer.m2_synthetic_integration",
    "pdu_exam_observer.m2_synthetic_nominal_fixture",
    "pdu_exam_observer.m2_synthetic_preflight_fixture",
    "pdu_exam_observer.m2_synthetic_reproduction",
    "pdu_exam_observer.m2_synthetic_review",
    "pydantic",
    "uvicorn",
]

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(web_dist), "assets/web"),
        (str(demo_dir), "demo"),
        *synthetic_binding_datas,
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDUExamObserver",
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PDU-Exam-Observer")
