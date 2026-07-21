from datetime import date

from app.agents.normalization_agent import NormalizationAgent
from app.db.models.transaction import Transaction

agent = NormalizationAgent()


def _candidate(transaction_date: date) -> Transaction:
    txn = Transaction()
    txn.transaction_date = transaction_date
    return txn


def test_detect_duplicate_matches_exact_date() -> None:
    candidates = [_candidate(date(2026, 1, 5))]
    match = agent._detect_duplicate(candidates, date(2026, 1, 5))
    assert match is candidates[0]


def test_detect_duplicate_matches_within_one_day_window() -> None:
    candidates = [_candidate(date(2026, 1, 5))]
    assert agent._detect_duplicate(candidates, date(2026, 1, 4)) is candidates[0]
    assert agent._detect_duplicate(candidates, date(2026, 1, 6)) is candidates[0]


def test_detect_duplicate_rejects_beyond_one_day_window() -> None:
    candidates = [_candidate(date(2026, 1, 5))]
    assert agent._detect_duplicate(candidates, date(2026, 1, 3)) is None
    assert agent._detect_duplicate(candidates, date(2026, 1, 7)) is None


def test_detect_duplicate_returns_none_for_no_candidates() -> None:
    assert agent._detect_duplicate([], date(2026, 1, 5)) is None


def test_detect_duplicate_picks_first_match_among_multiple_candidates() -> None:
    candidates = [_candidate(date(2026, 1, 1)), _candidate(date(2026, 1, 5))]
    match = agent._detect_duplicate(candidates, date(2026, 1, 6))
    assert match is candidates[1]
