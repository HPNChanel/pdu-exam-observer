"""Build the checked-in Colab notebook with all project training source embedded."""

from __future__ import annotations

import base64
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TRAINING_ROOT = Path(__file__).resolve().parent
EMBEDDED_FILES = (
    "research/training/__init__.py",
    "research/training/showcase/__init__.py",
    "research/training/showcase/v3/__init__.py",
    "research/training/showcase/v3/augmentation.py",
    "research/training/showcase/v3/calibration.py",
    "research/training/showcase/v3/dataset.py",
    "research/training/showcase/v3/evaluation.py",
    "research/training/showcase/v3/export_bundle.py",
    "research/training/showcase/v3/pipeline.py",
    "research/training/showcase/v3/protocol.py",
    "research/training/showcase/v3/splits.py",
    "research/training/showcase/v3/stgcn_mediapipe33.py",
    "src/pdu_exam_observer/__init__.py",
    "src/pdu_exam_observer/showcase/__init__.py",
    "src/pdu_exam_observer/showcase/export_contract.py",
    "src/pdu_exam_observer/showcase/model_import.py",
    "src/pdu_exam_observer/showcase/model_runtime.py",
    "src/pdu_exam_observer/showcase/preprocessing.py",
    "src/pdu_exam_observer/showcase/temporal_rules.py",
)


def _archive_b64() -> str:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in EMBEDDED_FILES:
            path = ROOT / name
            if not path.is_file():
                raise FileNotFoundError(f"required embedded source is missing: {name}")
            # Pinned metadata keeps the embedded archive byte-deterministic.
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return base64.b64encode(payload.getvalue()).decode("ascii")


def _code(source: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.splitlines()],
    }


def _markdown(source: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source.splitlines()],
    }


def build_notebook(destination: Path | None = None) -> Path:
    destination = destination or TRAINING_ROOT / "pdu_stgcn_training_colab.ipynb"
    requirements = (TRAINING_ROOT / "requirements-colab.txt").read_text(encoding="utf-8")
    archive = _archive_b64()
    archive_literal = "\n".join(
        f"    {archive[index : index + 76]!r}" for index in range(0, len(archive), 76)
    )
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "colab": {"name": "PDU_STGCN_TRAINING_SELF_CONTAINED.ipynb"},
        },
        "cells": [
            _markdown(
                "# PDU Exam Observer — self-contained ST-GCN training\n\n"
                "Two explicit modes are available. `SYNTHETIC_SMOKE` proves the CPU/GPU "
                "training → ONNX → bundle path and creates a `DEMO_ONLY` model. `RESEARCH` "
                "requires an allowlisted pose-only export plus a frozen protocol record. "
                "Raw video must never be uploaded. Outputs are evidence for human review, "
                "never automatic discipline or proof of research performance."
            ),
            _code(
                "from pathlib import Path\n\n"
                "PINNED_REQUIREMENTS = r'''\n" + requirements + "'''\n"
                "Path('/content/pdu-requirements.txt').write_text(PINNED_REQUIREMENTS)\n"
                "%pip install --quiet -r /content/pdu-requirements.txt"
            ),
            _code(
                "import base64\n"
                "import io\n"
                "import sys\n"
                "import zipfile\n\n"
                "PIPELINE_ARCHIVE_B64 = (\n" + archive_literal + "\n)\n"
                "WORK_ROOT = '/content/pdu-training'\n"
                "with zipfile.ZipFile(io.BytesIO(base64.b64decode(PIPELINE_ARCHIVE_B64))) as zf:\n"
                "    zf.extractall(WORK_ROOT)\n"
                "sys.path.insert(0, WORK_ROOT)\n"
                "sys.path.insert(0, WORK_ROOT + '/src')\n"
                "print('Embedded source restored; no repository or remote code fetched.')"
            ),
            _code(
                "MODE = 'SYNTHETIC_SMOKE'  # or 'RESEARCH'\n"
                "OUTPUT_ROOT = '/content/pdu-training-output'\n"
                "RESEARCH_EXPORT = None\n"
                "PROTOCOL_FREEZE = None\n"
                "if MODE not in {'SYNTHETIC_SMOKE', 'RESEARCH'}:\n"
                "    raise ValueError('MODE must be SYNTHETIC_SMOKE or RESEARCH')\n"
                "if MODE == 'RESEARCH' and (not RESEARCH_EXPORT or not PROTOCOL_FREEZE):\n"
                "    raise RuntimeError(\n"
                "        'RESEARCH_EXPORT_REQUIRED: pose-only ZIP and '\n"
                "        'frozen protocol JSON required'\n"
                "    )"
            ),
            _code(
                "from pathlib import Path\n\n"
                "from research.training.showcase.v3.pipeline import (\n"
                "    run_research_training,\n"
                "    run_synthetic_smoke,\n"
                ")\n\n"
                "if MODE == 'SYNTHETIC_SMOKE':\n"
                "    delivery = run_synthetic_smoke(Path(OUTPUT_ROOT), epochs=1)\n"
                "else:\n"
                "    delivery = run_research_training(\n"
                "        Path(RESEARCH_EXPORT), Path(PROTOCOL_FREEZE), Path(OUTPUT_ROOT)\n"
                "    )\n"
                "print({\n"
                "    'model_zip': str(delivery.model_zip),\n"
                "    'reports_zip': str(delivery.reports_zip),\n"
                "})"
            ),
            _code(
                "from google.colab import files\n\n"
                "files.download(str(delivery.model_zip))\n"
                "files.download(str(delivery.reports_zip))"
            ),
        ],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return destination


if __name__ == "__main__":
    print(build_notebook())
