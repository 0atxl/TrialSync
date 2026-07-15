from __future__ import annotations

from collections.abc import Iterable

from trialsync.domain.types import TruthValue


def truth_not(value: TruthValue) -> TruthValue:
    if value is TruthValue.true:
        return TruthValue.false
    if value is TruthValue.false:
        return TruthValue.true
    return TruthValue.unknown


def truth_and(values: Iterable[TruthValue]) -> TruthValue:
    items = tuple(values)
    if any(item is TruthValue.false for item in items):
        return TruthValue.false
    if items and all(item is TruthValue.true for item in items):
        return TruthValue.true
    return TruthValue.unknown


def truth_or(values: Iterable[TruthValue]) -> TruthValue:
    items = tuple(values)
    if any(item is TruthValue.true for item in items):
        return TruthValue.true
    if items and all(item is TruthValue.false for item in items):
        return TruthValue.false
    return TruthValue.unknown
