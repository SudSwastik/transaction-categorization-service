from decimal import Decimal

import pytest

from app.agents.normalization_agent import NormalizationAgent

agent = NormalizationAgent()


@pytest.mark.parametrize(
    ("raw_description", "expected"),
    [
        ("POS STARBUCKS #4471 SEATTLE WA", "Starbucks Seattle"),
        ("SQ *BLUE BOTTLE COFFEE", "Blue Bottle Coffee"),
        ("CHECKCARD 0104 WALMART SUPERCENTER", "Walmart Supercenter"),
        ("PYPL *ETSY MARKETPLACE", "Etsy Marketplace"),
        ("TST* THE CORNER BISTRO", "The Corner Bistro"),
        ("ACH DEBIT COMCAST CABLE", "Comcast Cable"),
        ("RECURRING PAYMENT GYM MEMBERSHIP", "Gym Membership"),
        ("NETFLIX.COM", "Netflix.Com"),
    ],
)
def test_normalize_strips_prefixes_codes_and_locations(raw_description: str, expected: str) -> None:
    assert agent.normalize(raw_description) == expected


def test_normalize_falls_back_to_original_when_nothing_survives_stripping() -> None:
    assert agent.normalize("POS #1234") == "Pos #1234"


def test_normalize_collapses_whitespace() -> None:
    assert agent.normalize("  STARBUCKS    SEATTLE   WA  ") == "Starbucks Seattle"


@pytest.mark.parametrize(
    ("raw_description", "account_currency", "expected"),
    [
        ("$45.00 UBER TRIP", None, "USD"),
        ("₹999 SWIGGY ORDER", None, "INR"),
        ("EUR 12.50 CAFE PARIS", None, "EUR"),
        ("C$30.00 TIM HORTONS", None, "CAD"),
        ("GENERIC MERCHANT NO SYMBOL", "GBP", "GBP"),
        ("GENERIC MERCHANT NO SYMBOL", None, "INR"),  # settings.DEFAULT_BASE_CURRENCY
    ],
)
def test_detect_currency(raw_description: str, account_currency: str | None, expected: str) -> None:
    assert agent._detect_currency(raw_description, account_currency) == expected


async def test_normalize_amount_same_currency_is_passthrough() -> None:
    result = await agent._normalize_amount(Decimal("100.00"), "INR", "INR")
    assert result.amount_base == Decimal("100.00")
    assert result.fx_rate_used == Decimal(1)


async def test_normalize_amount_uses_fallback_rate_when_redis_has_no_cached_rate() -> None:
    result = await agent._normalize_amount(Decimal("100"), "USD", "INR", redis=None)
    assert result.fx_rate_used > Decimal(1)
    assert result.amount_base == Decimal("100") * result.fx_rate_used
