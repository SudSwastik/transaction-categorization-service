import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from redis.asyncio import Redis

from app.core.config import get_settings

# Common processor/network prefixes that precede the merchant name, not part of it.
_STRIP_PREFIX_RE = re.compile(
    r"^(POS|SQ|TST|SP|PYPL|PAYPAL|CHECKCARD|DEBIT CARD PURCHASE|PURCHASE AUTH"
    r"|ACH DEBIT|RECURRING PAYMENT)[\s*:\-]+",
    re.IGNORECASE,
)
_REF_NUMBER_RE = re.compile(r"#\d+|\b\d{4,}\b")  # store/auth/ref codes and dates like 20260105
_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b")
_TRAILING_STATE_RE = re.compile(r"\s+[A-Z]{2}$")
_WHITESPACE_RE = re.compile(r"\s+")

# Longer symbols first so "C$"/"A$" aren't swallowed by the plain "$" check.
_CURRENCY_SYMBOL_MAP: dict[str, str] = {
    "C$": "CAD",
    "A$": "AUD",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
}
_CURRENCY_CODE_RE = re.compile(r"\b(USD|EUR|GBP|INR|CAD|AUD)\b", re.IGNORECASE)

# Used only when Redis has no cached rate yet (populated later by the
# refresh_fx_rates maintenance task) — approximate, just keeps the pipeline
# functional before that task exists.
_FALLBACK_FX_RATES_TO_INR: dict[str, Decimal] = {
    "INR": Decimal(1),
    "USD": Decimal(83),
    "EUR": Decimal(90),
    "GBP": Decimal(105),
    "CAD": Decimal(61),
    "AUD": Decimal(55),
}


@dataclass(frozen=True, slots=True)
class NormalizedAmount:
    amount_base: Decimal
    fx_rate_used: Decimal
    fx_rate_date: date


class NormalizationAgent:
    """Cleans raw statement fields into the canonical form used for categorization
    and dedup: a stable merchant name, a detected transaction currency, and the
    amount converted into the tenant's base currency."""

    def normalize(self, raw_description: str) -> str:
        text = raw_description.strip()
        cleaned = _STRIP_PREFIX_RE.sub("", text)
        cleaned = _DATE_RE.sub("", cleaned)
        cleaned = _REF_NUMBER_RE.sub("", cleaned)
        cleaned = _TRAILING_STATE_RE.sub("", cleaned)
        cleaned = cleaned.strip(" *-:#")
        cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
        return (cleaned or text).title()

    def _detect_currency(self, raw_description: str, account_currency: str | None = None) -> str:
        for symbol, code in _CURRENCY_SYMBOL_MAP.items():
            if symbol in raw_description:
                return code

        match = _CURRENCY_CODE_RE.search(raw_description)
        if match is not None:
            return match.group(1).upper()

        if account_currency:
            return account_currency

        return get_settings().DEFAULT_BASE_CURRENCY

    async def _normalize_amount(
        self,
        raw_amount: Decimal,
        source_currency: str,
        base_currency: str,
        redis: Redis | None = None,
    ) -> NormalizedAmount:
        today = date.today()
        if source_currency == base_currency:
            return NormalizedAmount(amount_base=raw_amount, fx_rate_used=Decimal(1), fx_rate_date=today)

        rate = await self._get_fx_rate(source_currency, base_currency, redis)
        amount_base = (raw_amount * rate).quantize(Decimal("0.0001"))
        return NormalizedAmount(amount_base=amount_base, fx_rate_used=rate, fx_rate_date=today)

    async def _get_fx_rate(
        self, source_currency: str, base_currency: str, redis: Redis | None
    ) -> Decimal:
        if redis is not None:
            cached = await redis.get(f"fx_rate:{source_currency}:{base_currency}")
            if cached is not None:
                value = cached.decode() if isinstance(cached, bytes) else cached
                return Decimal(value)

        source_to_inr = _FALLBACK_FX_RATES_TO_INR.get(source_currency, Decimal(1))
        base_to_inr = _FALLBACK_FX_RATES_TO_INR.get(base_currency, Decimal(1))
        return (source_to_inr / base_to_inr).quantize(Decimal("0.00000001"))
