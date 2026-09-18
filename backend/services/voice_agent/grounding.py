"""
services/voice_agent/grounding.py — did anything the agent said come from nowhere?

The gates in _execute_tool stop the agent DOING things it should not. They do
nothing about the agent SAYING things that were never true. A quoted rate, a
date, a booking reference — spoken confidently, traceable to no tool result, no
page of the business's own knowledge base, and nothing the caller said — is a
promise the motel then has to honour or explain away.

This is the check, and it is deliberately only a check to begin with. The plan
for it says: flag it, log it, measure the rate, and decide afterwards whether
blocking is worth what blocking costs. A false flag here would gag an agent
mid-sentence, so the rate has to be known before anything is wired to it.

What counts as a source, in order of how much it can be trusted:

  a tool result from THIS call   the reservation, the availability answer
  the caller's own words         they said "the 10th of September" first
  the business knowledge base    room rates and policies, static and true

Anything else is unsourced. Note that unsourced is not the same as wrong — the
model may repeat a rate it saw two turns ago whose tool result has since been
dropped. That is exactly why this measures before it blocks.
"""

import re

# CC-76818, cc 76818, CC76818 — the reference is the highest-value claim here
# because there is no way to say one by accident and no way for a caller to
# verify it in the moment.
_REFERENCE = re.compile(r"\bCC[-\s]?(\d{4,6})\b", re.IGNORECASE)

# $135, $1,240.00, 135 dollars
_MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)|\b(\d[\d,]*(?:\.\d{1,2})?)\s+dollars\b",
                    re.IGNORECASE)

# Every number anywhere, for building the set of amounts a source vouches for.
_ANY_NUMBER = re.compile(r"\d[\d,]*(?:\.\d{1,2})?")

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "sept": 9, "october": 10,
    "november": 11, "december": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

# "the 4th of September", "September 4th", "September 4"
_SPOKEN_DATE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_ALT})\b"
    rf"|\b({_MONTH_ALT})\s+(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b\d{4}-(\d{2})-(\d{2})\b")


def _clean_number(raw: str) -> str:
    """135 / 1,240 / 270.00 all compare as the same kind of thing."""
    value = raw.replace(",", "")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value


def _dates_in(text: str) -> set:
    """(month, day) pairs, however the text happens to write them."""
    found = set()
    for m_month, m_day in _ISO_DATE.findall(text):
        found.add((int(m_month), int(m_day)))
    for day_a, month_a, month_b, day_b in _SPOKEN_DATE.findall(text):
        if month_a:
            found.add((_MONTHS[month_a.lower()], int(day_a)))
        else:
            found.add((_MONTHS[month_b.lower()], int(day_b)))
    return found


def _references_in(text: str) -> set:
    return {digits for digits in _REFERENCE.findall(text)}


def _money_in(text: str) -> set:
    return {_clean_number(a or b) for a, b in _MONEY.findall(text)}


def unsourced_claims(spoken: str, sources) -> list:
    """
    The specific claims in `spoken` that appear in none of `sources`.

    Returns a list of (kind, claim) — "reference", "money" or "date" — so the
    three can be counted separately. They are not equally serious: an invented
    reference is a fabricated record, an invented rate is a mispriced stay, and
    an invented date is usually the model restating something slightly wrong.

    `spoken` must be the model's own text, BEFORE it is prepared for speech —
    the TTS sanitiser turns "$135" into "one hundred and thirty five dollars"
    and "2/07" into a spoken date, and none of the patterns here would survive
    that. Checking the wrong end of that pipeline is the easy mistake.
    """
    if not spoken:
        return []
    corpus = "\n".join(str(s) for s in sources if s)

    ok_numbers = {_clean_number(n) for n in _ANY_NUMBER.findall(corpus)}
    ok_references = _references_in(corpus)
    ok_dates = _dates_in(corpus)

    claims = []
    for digits in sorted(_references_in(spoken)):
        if digits not in ok_references:
            claims.append(("reference", f"CC-{digits}"))
    for amount in sorted(_money_in(spoken)):
        if amount not in ok_numbers:
            claims.append(("money", f"${amount}"))
    for month, day in sorted(_dates_in(spoken)):
        if (month, day) not in ok_dates:
            claims.append(("date", f"{day:02d}/{month:02d}"))
    return claims


def business_facts() -> list:
    """
    The tenant's own knowledge base, flattened, as a source.

    The room rates live in the system prompt, so an agent quoting $135 a night
    is not inventing anything — and a check that flagged it would be measuring
    its own ignorance. Loaded lazily: this module is imported by tests that
    have no business touching tenant data.
    """
    try:
        from services.knowledge_base.coalcreek import COALCREEK_DATA
        return [str(COALCREEK_DATA)]
    except Exception:
        return []
