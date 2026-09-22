import os
import sys

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "authority":
        from pdu_exam_observer.research_runtime.authority_cli import main as authority_main

        raise SystemExit(authority_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "authority-template":
        from pdu_exam_observer.research_runtime.authority_cli import template_main

        raise SystemExit(template_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "workspace":
        from pdu_exam_observer.workspace_cli import main as workspace_main

        workspace_main(sys.argv[2:])
        raise SystemExit(0)
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
