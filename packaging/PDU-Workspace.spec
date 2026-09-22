"""Current research workspace; runtime-only environment, no training framework payload."""
import os
from pathlib import Path

from PyInstaller.building.build_main import COLLECT, EXE, PYZ, Analysis
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(os.environ["PDU_PROJECT_ROOT"]).resolve(strict=True)
ffmpeg = Path(os.environ["PDU_FFMPEG_BINARY"]).resolve(strict=True)
datas = [
    (str(root / "apps/web/dist"), "assets/web"),
    (str(root / "demo"), "demo"),
    (str(root / "src/pdu_exam_observer/assets/models"), "pdu_exam_observer/assets/models"),
    *collect_data_files("mediapipe"),
    *collect_data_files("onnxruntime"),
    *collect_data_files("onnx", excludes=["backend/test/**", "test/**", "defs/training/**"]),
]
a = Analysis(
    [str(root / "src/pdu_exam_observer/__main__.py")],
    pathex=[str(root / "src")],
    binaries=[(str(ffmpeg), "tools")], datas=datas,
    hiddenimports=[*collect_submodules("pdu_exam_observer.research_runtime"),
                   *collect_submodules("pdu_exam_observer.showcase"),
                   # NumPy >=2.3 imports this from C; the NumPy-supplied hook omits it.
                   "numpy._core._exceptions",
                   "pdu_exam_observer.workspace_cli", "pdu_exam_observer.workspace_service",
                   "pdu_exam_observer.api.workspace", "onnx", "uvicorn.logging", "uvicorn.loops.auto",
                   "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto",
                   "uvicorn.lifespan.on"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["torch", "onnxscript", "sklearn", "scipy", "matplotlib", "research.training"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDUWorkspace", console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PDU-Workspace")
