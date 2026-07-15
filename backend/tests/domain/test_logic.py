import pytest

from trialsync.domain.logic import truth_and, truth_not, truth_or
from trialsync.domain.types import TruthValue


@pytest.mark.parametrize(
    ("left", "right", "expected_and", "expected_or"),
    [
        (TruthValue.true, TruthValue.true, TruthValue.true, TruthValue.true),
        (TruthValue.true, TruthValue.false, TruthValue.false, TruthValue.true),
        (TruthValue.true, TruthValue.unknown, TruthValue.unknown, TruthValue.true),
        (TruthValue.false, TruthValue.true, TruthValue.false, TruthValue.true),
        (TruthValue.false, TruthValue.false, TruthValue.false, TruthValue.false),
        (TruthValue.false, TruthValue.unknown, TruthValue.false, TruthValue.unknown),
        (TruthValue.unknown, TruthValue.true, TruthValue.unknown, TruthValue.true),
        (TruthValue.unknown, TruthValue.false, TruthValue.false, TruthValue.unknown),
        (TruthValue.unknown, TruthValue.unknown, TruthValue.unknown, TruthValue.unknown),
    ],
)
def test_and_or_truth_tables(
    left: TruthValue,
    right: TruthValue,
    expected_and: TruthValue,
    expected_or: TruthValue,
) -> None:
    assert truth_and((left, right)) is expected_and
    assert truth_or((left, right)) is expected_or


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (TruthValue.true, TruthValue.false),
        (TruthValue.false, TruthValue.true),
        (TruthValue.unknown, TruthValue.unknown),
    ],
)
def test_not_truth_table(value: TruthValue, expected: TruthValue) -> None:
    assert truth_not(value) is expected
