M2-S3E CLEAN-ENVIRONMENT HANDOFF — NOT A RELEASE

SYNTHETIC M2 ONLY
SAME-HOST PORTABILITY EVIDENCE IS NOT CLEAN-MACHINE VERIFICATION
NO CAMERA OR DEVICE VERIFICATION
NO D1_GO
NO PARTICIPANT COLLECTION AUTHORITY
NO INTERNET OR ADMINISTRATOR RIGHTS REQUIRED
CLEAN-MACHINE RESPONSE REQUIRES LATER SOURCE IMPORT VALIDATION
UNSIGNED

Run only from the extracted handoff root with Windows PowerShell 5.1:

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\VERIFY_M2_S3E_CLEAN_ENVIRONMENT.ps1

The verifier accepts no arguments. It runs packaged synthetic fixtures only,
uses loopback networking, and writes M2_S3E_CLEAN_ENVIRONMENT_RESPONSE.json.
That response remains UNVERIFIED_PENDING_SOURCE_IMPORT until a separate S3E-B
task validates evidence returned from a different Windows environment.
