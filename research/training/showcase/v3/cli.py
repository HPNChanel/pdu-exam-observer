"""Command-line entrypoint for local/Colab training delivery."""

from __future__ import annotations

import argparse
from pathlib import Path

from .build_self_contained_notebook import build_notebook
from .pipeline import run_research_training, run_synthetic_smoke


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("SYNTHETIC_SMOKE", "RESEARCH"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--protocol-freeze", type=Path)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--build-notebook", action="store_true")
    args = parser.parse_args()
    if args.build_notebook:
        build_notebook()
    if args.mode == "SYNTHETIC_SMOKE":
        delivery = run_synthetic_smoke(args.output, epochs=args.epochs)
    else:
        if args.export is None or args.protocol_freeze is None:
            parser.error("RESEARCH requires --export and --protocol-freeze")
        delivery = run_research_training(
            args.export, args.protocol_freeze, args.output, epochs=args.epochs
        )
    print(delivery.model_zip)
    print(delivery.reports_zip)


if __name__ == "__main__":
    main()
