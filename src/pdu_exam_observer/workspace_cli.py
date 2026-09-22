"""Native entrypoint: private storage and credentials never originate in browser input."""

import argparse
import getpass
import os
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PDU local research workspace")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    root = (
        args.root
        or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "PDUExamObserver" / "workspace"
    )
    if not root.is_absolute() or str(root).startswith("\\\\"):
        parser.error("--root must be an absolute local directory")
    os.environ["PDU_WORKSPACE_ROOT"] = str(root)
    os.environ["PDU_RUNTIME_MODE"] = "m2research"
    if args.no_browser:
        os.environ["PDU_OPEN_BROWSER"] = "0"
    if not os.environ.get("PDU_REVIEWER_PIN"):
        pin = getpass.getpass("PIN cho phien lam viec nay (khong luu tren dia): ")
        if len(pin) < 6:
            parser.error("PIN must contain at least six characters")
        os.environ["PDU_REVIEWER_PIN"] = pin
    from pdu_exam_observer.launcher import main as launch

    try:
        launch()
    finally:
        os.environ.pop("PDU_REVIEWER_PIN", None)


if __name__ == "__main__":
    main()
