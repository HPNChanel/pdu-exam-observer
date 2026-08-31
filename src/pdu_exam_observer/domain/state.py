from pdu_exam_observer.contracts import SessionState


class InvalidTransition(ValueError):
    """Raised when a session state cannot move to its requested target."""


_TRANSITIONS: dict[tuple[SessionState, str], SessionState] = {
    (SessionState.DRAFT, "consent"): SessionState.CONSENT_CONFIRMED,
    (SessionState.CONSENT_CONFIRMED, "preflight"): SessionState.PREFLIGHT_READY,
    (SessionState.PREFLIGHT_READY, "start"): SessionState.RECORDING,
    (SessionState.RECORDING, "stop"): SessionState.SEALED,
}


def transition(current: SessionState, action: str) -> SessionState:
    target = _TRANSITIONS.get((current, action))
    if target is not None:
        return target
    if (current, action) in {
        (SessionState.CONSENT_CONFIRMED, "consent"),
        (SessionState.PREFLIGHT_READY, "preflight"),
        (SessionState.RECORDING, "start"),
        (SessionState.SEALED, "stop"),
    }:
        return current
    raise InvalidTransition(f"Cannot {action} session in {current} state")
