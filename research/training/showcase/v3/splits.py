"""Deterministic participant-disjoint outer folds and provenance gates."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

_PARTICIPANT_ID = re.compile(r"^P(?:0[1-9]|1[0-2])$")
_PILOT_IDS = frozenset({"P01", "P02"})


@dataclass(frozen=True, slots=True)
class OuterFold:
    index: int
    train: tuple[str, ...]
    calibration: tuple[str, ...]
    test: tuple[str, ...]


def _order_key(protocol_version: str, participant: str) -> str:
    return hashlib.sha256(f"{protocol_version}:{participant}".encode()).hexdigest()


def build_outer_folds(
    participants: tuple[str, ...], *, protocol_version: str
) -> tuple[OuterFold, ...]:
    """Build five folds from ten confirmatory people, ignoring exactly P01/P02 pilot IDs."""

    if not protocol_version or len(protocol_version) > 128:
        raise ValueError("protocol_version is required")
    if len(set(participants)) != len(participants):
        raise ValueError("participant IDs must be unique")
    if any(_PARTICIPANT_ID.fullmatch(value) is None for value in participants):
        raise ValueError("participant IDs must be pseudonyms P01 through P12")
    confirmatory = tuple(value for value in participants if value not in _PILOT_IDS)
    if len(confirmatory) != 10 or set(participants) != set(confirmatory) | _PILOT_IDS:
        raise ValueError("P01/P02 pilot and P03-P12 confirmatory participants are required")
    ordered = tuple(sorted(confirmatory, key=lambda value: _order_key(protocol_version, value)))
    pairs = tuple(tuple(ordered[index : index + 2]) for index in range(0, 10, 2))
    folds: list[OuterFold] = []
    for index in range(5):
        test = pairs[index]
        calibration = pairs[(index + 1) % 5]
        held_out = set(test) | set(calibration)
        train = tuple(value for value in ordered if value not in held_out)
        folds.append(OuterFold(index=index, train=train, calibration=calibration, test=test))
    return tuple(folds)


def validate_fold_samples(samples: Iterable[Mapping[str, object]], fold: OuterFold) -> None:
    """Reject pilot leakage, source leakage, and orphan augmented records."""

    records = tuple(samples)
    identifiers = {record.get("sample_id") for record in records}
    if None in identifiers or len(identifiers) != len(records):
        raise ValueError("sample IDs must be present and unique")
    for record in records:
        participant = record.get("participant_pseudonym")
        source_kind = record.get("source_kind")
        cohort = record.get("cohort")
        if participant in _PILOT_IDS or cohort == "PILOT":
            raise ValueError("pilot samples are excluded from confirmatory folds")
        if participant in fold.calibration or participant in fold.test:
            if source_kind != "REAL":
                raise ValueError("calibration and test samples must be REAL")
        elif participant not in fold.train:
            raise ValueError("sample participant is outside the fold")
        if source_kind == "AUGMENTED":
            parent = record.get("parent_provenance_id")
            if not isinstance(parent, str) or not parent:
                raise ValueError("augmented samples require parent provenance")
