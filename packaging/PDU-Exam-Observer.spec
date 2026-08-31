# PyInstaller one-folder specification. Set PDU_ENTRY_SCRIPT, PDU_WEB_DIST,
# PDU_DEMO_DIR, and PDU_RELEASE_DIR from the release script.
from pathlib import Path
import os

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ


project_root = Path(SPECPATH).resolve().parent
entry_script = Path(os.environ.get("PDU_ENTRY_SCRIPT", "src/pdu_exam_observer/__main__.py"))
web_dist = Path(os.environ.get("PDU_WEB_DIST", "apps/web/dist"))
demo_dir = Path(os.environ.get("PDU_DEMO_DIR", "demo"))
release_dir = Path(os.environ.get("PDU_RELEASE_DIR", "packaging/release"))
if not entry_script.is_absolute():
    entry_script = project_root / entry_script
if not web_dist.is_absolute():
    web_dist = project_root / web_dist
if not demo_dir.is_absolute():
    demo_dir = project_root / demo_dir
if not entry_script.is_file():
    raise SystemExit(f"PDU_ENTRY_SCRIPT does not exist: {entry_script}")
if not web_dist.is_dir():
    raise SystemExit(f"PDU_WEB_DIST does not exist; run the frontend build first: {web_dist}")
if not demo_dir.is_dir():
    raise SystemExit(f"PDU_DEMO_DIR does not exist: {demo_dir}")

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[(str(web_dist), "assets/web"), (str(demo_dir), "demo")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="PDUExamObserver", console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PDU-Exam-Observer")
