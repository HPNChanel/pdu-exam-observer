from __future__ import annotations

import json
import zipfile
from pathlib import Path

from research.training.showcase.v3.build_self_contained_notebook import build_notebook
from scripts.build_training_delivery import build_colab_delivery, build_preprocessing_fixture


def test_notebook_is_self_contained_pinned_and_gates_research_mode(tmp_path: Path) -> None:
    notebook_path = build_notebook(tmp_path / "pdu_training.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "SYNTHETIC_SMOKE" in source
    assert "RESEARCH" in source
    assert "RESEARCH_EXPORT_REQUIRED" in source
    assert "torch==2.13.0" in source
    assert "numpy==2.4.6" in source
    assert "git clone" not in source
    assert "trust_remote_code" not in source
    assert "huggingface_hub" not in source
    assert "PIPELINE_ARCHIVE_B64" in source


def test_colab_delivery_includes_pinned_inputs_templates_and_restore_guide(
    tmp_path: Path,
) -> None:
    build_preprocessing_fixture()
    build_notebook()

    delivery = build_colab_delivery(tmp_path / "colab-delivery.zip")

    with zipfile.ZipFile(delivery) as archive:
        assert set(archive.namelist()) == {
            "NOTICE.md",
            "TRAINING_README.md",
            "fixtures/preprocessing_golden.manifest.json",
            "fixtures/preprocessing_golden.npz",
            "fixtures/synthetic_smoke_input.manifest.json",
            "fixtures/synthetic_smoke_input.npz",
            "hf_source_lock.json",
            "pdu_stgcn_training_colab.ipynb",
            "protocol-freeze.template.json",
            "requirements-colab.txt",
            "training_config.json",
        }
        guide = archive.read("TRAINING_README.md").decode()
        assert "Restore and import" in guide
        assert "Never upload raw video" in guide
