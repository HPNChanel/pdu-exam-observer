from __future__ import annotations

import json
import zipfile
from pathlib import Path

from research.training.showcase.v3.build_self_contained_notebook import (
    TRAINING_ROOT,
    build_notebook,
)
from scripts.build_training_delivery import (
    DEFAULT_FIXTURE_ROOT,
    build_colab_delivery,
    build_preprocessing_fixture,
)


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


def test_checked_in_artifacts_match_a_fresh_deterministic_build(tmp_path: Path) -> None:
    """The committed notebook and golden fixture must equal a fresh build byte-for-byte.

    A drift here means somebody edited the embedded pipeline or preprocessing
    without regenerating the shipped artifacts — the test must fail, not
    silently regenerate them in-tree.
    """
    fixture_root = tmp_path / "fixtures"
    fixture, manifest = build_preprocessing_fixture(fixture_root)
    notebook = build_notebook(tmp_path / "pdu_stgcn_training_colab.ipynb")

    assert fixture.read_bytes() == (
        DEFAULT_FIXTURE_ROOT / "preprocessing_golden.npz"
    ).read_bytes()
    assert manifest.read_bytes() == (
        DEFAULT_FIXTURE_ROOT / "preprocessing_golden.manifest.json"
    ).read_bytes()
    assert notebook.read_bytes() == (
        TRAINING_ROOT / "pdu_stgcn_training_colab.ipynb"
    ).read_bytes()


def test_colab_delivery_includes_pinned_inputs_templates_and_restore_guide(
    tmp_path: Path,
) -> None:
    build_preprocessing_fixture(tmp_path / "fixtures")
    delivery = build_colab_delivery(
        tmp_path / "colab-delivery.zip", fixture_root=tmp_path / "fixtures"
    )

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
        golden = archive.read("fixtures/preprocessing_golden.npz")
        assert golden == (DEFAULT_FIXTURE_ROOT / "preprocessing_golden.npz").read_bytes()
