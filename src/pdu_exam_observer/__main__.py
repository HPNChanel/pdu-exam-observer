import os
import sys

if __name__ == "__main__":
    if os.getenv("PDU_RUNTIME_MODE", "").lower() == "m2synthetic-reproduce":
        from pdu_exam_observer.m2_packaged_reproduction import main as reproduction_main

        raise SystemExit(reproduction_main(sys.argv[1:]))
    if len(sys.argv) > 1 and sys.argv[1] in {"migrate-r1", "rehearse-r1"}:
        from pdu_exam_observer.m1_r1_cli import cli_main

        raise SystemExit(cli_main(sys.argv[1:]))
    if len(sys.argv) > 1 and sys.argv[1] == "configure":
        from pdu_exam_observer.configuration import configure_main

        configure_main(sys.argv[2:])
    else:
        from pdu_exam_observer.launcher import main

        main()
