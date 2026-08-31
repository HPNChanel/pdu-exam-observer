import sys

from pdu_exam_observer.configuration import configure_main
from pdu_exam_observer.launcher import main
from pdu_exam_observer.m1_r1_cli import cli_main

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"migrate-r1", "rehearse-r1"}:
        raise SystemExit(cli_main(sys.argv[1:]))
    if len(sys.argv) > 1 and sys.argv[1] == "configure":
        configure_main(sys.argv[2:])
    else:
        main()
