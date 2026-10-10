"""
How callers say dates, read the way a receptionist reads them.

Callers rarely say "the 23rd of October". They say "next weekend", "Friday
week", "the weekend after", "in a fortnight", "end of the month", "the 5th",
"Friday the 17th", "Christmas", "a couple of nights". The model turns those
into ISO dates itself, from a calendar in its prompt, and it gets them wrong in
ways nobody hears: the prompt used to tell it that "this weekend" and "next
weekend" are the same dates, and that "next Monday" is both the nearest Monday
and the one in next week.

This module reads the caller's own words deterministically, so the tool can
check the model's dates against what the caller actually said. It is built to
be wrong rarely rather than to be right often:

  * One date expression, or two joined into a range ("Friday to Sunday"), is
    read. Anything else ("the 10th to the 12th, can I check in tomorrow if I'm
    early?") is NOT read — a passing mention of another day is not the caller
    changing their dates.
  * A phrase people genuinely use two ways ("next Friday" said on a Wednesday)
    comes back with BOTH readings, so the agent confirms instead of guessing.
  * A contradiction ("Friday the 17th" when the 17th is a Saturday) comes back
    as a conflict, so the agent asks.
  * A phrase that names a period, not a day ("next week", "mid November")
    comes back as a span; the agent must not invent a day inside it.
  * Talk about the past ("when we stayed last weekend") is marked past and
    never used to book.

Pure functions, no I/O: `read_dates(text, today)` and `reconcile(...)`.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]

# Full words only. Speech-to-text writes days and months out in full, and the
# short forms are ordinary words ("we sat", "the sun", "Jan", "a mar").
_WEEKDAY_RE = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
# "may" is left out of the bare-month alternation on purpose: "I may stay two
# nights" is not a month. May still matches with a day next to it ("May 5th",
# "the 5th of May").
_MONTH_RE = (r"(?:january|february|march|april|june|july|august|september|october"
             r"|november|december)")
_MONTH_WITH_MAY_RE = r"(?:may|" + _MONTH_RE[3:]

_SHARED_MONTH_RANGE = re.compile(
    rf"\b(?:(?P<w1>{_WEEKDAY_RE})\s+)?(?:the\s+)?(?P<a>\d{{1,2}})(?:st|nd|rd|th)?\s*(?:-|to|till|until|through|and)\s*"
    rf"(?:(?P<w2>{_WEEKDAY_RE})\s+)?(?:the\s+)?(?P<b>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<m>{_MONTH_WITH_MAY_RE})\b")

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "fourteen": 14, "a couple of": 2, "a couple": 2, "couple of": 2,
}
_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "twenty first": 21, "twenty second": 22,
    "twenty third": 23, "twenty fourth": 24, "twenty fifth": 25, "twenty sixth": 26,
    "twenty seventh": 27, "twenty eighth": 28, "twenty ninth": 29, "thirtieth": 30,
    "thirty first": 31,
}


@dataclass(frozen=True)
class DateReading:
    """What the caller's words say about the stay. Every field is optional."""
    phrase: str = ""
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    # The other sensible check-in when people use the phrase two ways.
    alternative: Optional[date] = None
    # A period with no day in it: "next week", "mid November".
    span: Optional[tuple] = None
    nights: Optional[int] = None
    past: bool = False
    conflict: str = ""
    weekend: bool = False

    @property
    def ambiguous(self) -> bool:
        return self.alternative is not None


# ── calendar helpers ─────────────────────────────────────────────────────────

def _upcoming(today: date, weekday: int, include_today: bool) -> date:
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not include_today:
        delta = 7
    return today + timedelta(days=delta)


def _this_saturday(today: date) -> date:
    """Saturday of 'this weekend'. On a Sunday the weekend in progress is
    nearly over, so 'this weekend' is the coming one (matches the old resolver)."""
    return _upcoming(today, 5, include_today=True)


def _saturday_of(day: date) -> date:
    """The Saturday of the weekend a date sits in or leads into."""
    if day.weekday() == 6:
        return day - timedelta(days=1)
    return _upcoming(day, 5, include_today=True)


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _add_months(today: date, n: int) -> tuple:
    m = today.month - 1 + n
    return today.year + m // 12, m % 12 + 1


def _next_dated(today: date, month: int, day: int) -> Optional[date]:
    """Nearest future (or today) occurrence of month/day; None if it never exists."""
    for year in (today.year, today.year + 1, today.year + 2, today.year + 3, today.year + 4):
        try:
            d = date(year, month, day)
        except ValueError:
            continue  # 29 Feb in a non-leap year
        if d >= today:
            return d
    return None


def _next_day_of_month(today: date, day: int) -> Optional[date]:
    """'the 5th': this month if it hasn't passed, otherwise the next month that has one."""
    for n in range(0, 13):
        y, m = _add_months(today, n)
        if day <= calendar.monthrange(y, m)[1]:
            d = date(y, m, day)
            if d >= today:
                return d
    return None


def _easter(year: int) -> date:
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


# Victoria, where the motel is. "Long weekend" is deliberately absent: which one
# depends on the month and the state, so it is asked about, not guessed.
_HOLIDAYS = {
    r"christmas eve": lambda y: date(y, 12, 24),
    r"christmas(?: day)?|xmas": lambda y: date(y, 12, 25),
    r"boxing day": lambda y: date(y, 12, 26),
    r"new year'?s eve": lambda y: date(y, 12, 31),
    r"new year'?s(?: day)?": lambda y: date(y, 1, 1),
    r"australia day": lambda y: date(y, 1, 26),
    r"anzac day": lambda y: date(y, 4, 25),
    r"valentine'?s(?: day)?": lambda y: date(y, 2, 14),
    r"good friday": lambda y: _easter(y) - timedelta(days=2),
    r"easter (?:saturday)": lambda y: _easter(y) - timedelta(days=1),
    r"easter sunday": lambda y: _easter(y),
    r"easter monday": lambda y: _easter(y) + timedelta(days=1),
    r"easter(?: weekend)?": lambda y: _easter(y) - timedelta(days=2),
    r"melbourne cup(?: day)?": lambda y: _nth_weekday(y, 11, 1, 1),
    r"king'?s birthday": lambda y: _nth_weekday(y, 6, 0, 2),
    r"labour day": lambda y: _nth_weekday(y, 3, 0, 2),
}


def _next_holiday(today: date, fn) -> date:
    d = fn(today.year)
    return d if d >= today else fn(today.year + 1)


# ── text normalisation ───────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    t = (text or "").lower().replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"[,!?;:]", " ", t)
    t = re.sub(r"\.(?=\s|$)", " ", t)
    for words, n in sorted(_ORDINAL_WORDS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b{words.replace(' ', '[ -]')}\b", f"{n}{_suffix(n)}", t)
    t = re.sub(r"\b(\d{1,2})\s+(st|nd|rd|th)\b", r"\1\2", t)  # STT: "17 th"
    t = re.sub(r"\s+", " ", t).strip()
    # "the 24th to the 26th of November": the month belongs to BOTH days. Read
    # alone, "the 24th" was the next 24th (October), so a three-night stay in
    # November became 33 nights from October.
    return _SHARED_MONTH_RANGE.sub(_share_month, t)


def _share_month(m) -> str:
    whole = m.group(0)
    has_suffix = bool(re.search(r"\d(?:st|nd|rd|th)\b", whole))
    rest = m.string[m.end():]
    # Leave it alone unless it is plainly a pair of days: "ages 5 to 7 may come",
    # "rooms 2 to 4 may be free", "kids are 3 and 5, november 20th we arrive".
    if (m["m"] == "may" and not (has_suffix or re.search(r"\bof\s+may\b", whole))) \
            or (re.search(r"\s(?:and)\s", whole) and not has_suffix) \
            or re.match(r"\s+\d", rest) or (not has_suffix and "the" not in whole.split()):
        return whole
    w1 = f"{m['w1']} " if m["w1"] else ""
    w2 = f"{m['w2']} " if m["w2"] else ""
    a, b = int(m["a"]), int(m["b"])
    return f"{w1}the {a}{_suffix(a)} of {m['m']} to {w2}the {b}{_suffix(b)} of {m['m']}"


def _suffix(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _weekday_index(word: str) -> int:
    return WEEKDAYS.index(word.lower())


def _month_index(word: str) -> int:
    return MONTHS.index(word.lower()) + 1


def _count(word: str) -> Optional[int]:
    word = word.strip()
    if word.isdigit():
        return int(word)
    return _NUMBER_WORDS.get(word)


# ── expression finders ───────────────────────────────────────────────────────
# Each returns (start, end, Point) for every match. A Point is one candidate
# check-in, or a span, plus the other reading where the phrase is two-way.

@dataclass(frozen=True)
class _Point:
    day: Optional[date] = None
    alternative: Optional[date] = None
    span: Optional[tuple] = None
    weekend: bool = False
    conflict: str = ""
    kind: str = ""   # "weekday" | "dom" (day of month) | "dated" (day + month) | "veto" | ""


_VETO = _Point(kind="veto")   # words that are about dates, but not ones we can read safely


_COUNT_RE = r"(\d{1,2}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fourteen)"

_PATTERNS = []


def _pattern(regex):
    def register(fn):
        _PATTERNS.append((re.compile(regex), fn))
        return fn
    return register


@_pattern(rf"\b(?:(?P<wd>{_WEEKDAY_RE})\s+)?(?:the\s+)?(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?"
          rf"(?P<m>{_MONTH_WITH_MAY_RE})\b(?:\s+(?P<y>20\d\d))?")
def _day_month(m, today, anchor):
    if m["m"] == "may" and not re.search(r"(?:st|nd|rd|th)\b|\bthe\b|\bof\b", m.group(0)):
        return None   # "ages 5 to 7 may come"
    return _dated(m, today, int(m["d"]), _month_index(m["m"]))


@_pattern(rf"\b(?:(?P<wd>{_WEEKDAY_RE})\s+)?(?P<m>{_MONTH_WITH_MAY_RE})\s+(?:the\s+)?(?P<d>\d{{1,2}})"
          rf"(?:st|nd|rd|th)?\b(?:\s+(?P<y>20\d\d))?")
def _month_day(m, today, anchor):
    if m["m"] == "may" and not re.search(r"(?:st|nd|rd|th)\b|\bthe\b", m.group(0)):
        return None   # "may 2 people stay"
    return _dated(m, today, int(m["d"]), _month_index(m["m"]))


def _dated(m, today, day, month):
    year = m.groupdict().get("y")
    if year:
        try:
            d = date(int(year), month, day)
        except ValueError:
            return _Point(conflict=f"there is no {day}{_suffix(day)} of {MONTHS[month - 1].title()}")
    else:
        d = _next_dated(today, month, day)
        if d is None:
            return _Point(conflict=f"there is no {day}{_suffix(day)} of {MONTHS[month - 1].title()}")
    return _with_weekday_check(m, d, "dated")


# Not "the 2nd floor", "the 1st night", "the first time": an ordinal that names
# something else is not a date.
_NOT_A_DATE_AFTER = (r"(?!\s+(?:floor|room|one|person|people|guest|bed|night|nights|time|option|choice"
                     r"|car|level|name|bedroom|child|kid|adult|week|weekend|month|day|of\s+next\s+month"
                     r"|available|ones?|of\s+(?:those|them|these|the)\b))")


@_pattern(rf"\b(?:(?P<wd>{_WEEKDAY_RE})\s+)?the\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)\b{_NOT_A_DATE_AFTER}")
def _bare_ordinal(m, today, anchor):
    day = int(m["d"])
    if not 1 <= day <= 31:
        return None
    d = _next_day_of_month(today, day)
    if d is None:
        return None
    return _with_weekday_check(m, d, "dom")


@_pattern(r"\bthe\s+(?P<d>\d{1,2})(?:st|nd|rd|th)\s+of\s+next\s+month\b")
def _ordinal_next_month(m, today, anchor):
    y, mo = _add_months(today, 1)
    day = int(m["d"])
    if not 1 <= day <= calendar.monthrange(y, mo)[1]:
        return _Point(conflict=f"next month has no {day}{_suffix(day)}")
    return _Point(day=date(y, mo, day), kind="dated")


def _with_weekday_check(m, d, kind):
    wd = m.groupdict().get("wd")
    if wd and _weekday_index(wd) != d.weekday():
        said = WEEKDAYS[_weekday_index(wd)].title()
        # The said weekday nearest the said date: "Friday the 17th" when the
        # 17th is a Saturday is most likely Friday the 16th.
        options = [d + timedelta(days=k) for k in range(-3, 4)
                   if (d + timedelta(days=k)).weekday() == _weekday_index(wd)]
        near = min(options, key=lambda o: abs((o - d).days))
        return _Point(day=d, alternative=near, kind=kind,
                      conflict=f"the {d.day}{_suffix(d.day)} is a {WEEKDAYS[d.weekday()].title()}, not a {said}")
    return _Point(day=d, kind=kind)


@_pattern(r"\b(?:the\s+)?day\s+after\s+tomorrow\b")
def _day_after_tomorrow(m, today, anchor):
    return _Point(day=today + timedelta(days=2))


@_pattern(r"\b(?:tomorrow(?:\s+night)?|tmrw)\b")
def _tomorrow(m, today, anchor):
    return _Point(day=today + timedelta(days=1))


@_pattern(r"\b(?:today|tonight|this\s+evening|this\s+arvo|this\s+afternoon)\b")
def _today(m, today, anchor):
    return _Point(day=today)


@_pattern(r"\b(?:this\s+time\s+next\s+week|a\s+week\s+(?:from\s+)?today|in\s+a\s+week(?:'s)?(?:\s+time)?"
          r"|a\s+week\s+from\s+now|in\s+(?:a\s+)?fortnight|a\s+fortnight\s+(?:from\s+)?(?:today|now)"
          r"|in\s+(?P<n>\d{1,2}|a|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?P<u>days?|weeks?|fortnights?)"
          r"(?:'s)?(?:\s+time)?|(?P<n2>\d{1,2}|two|three|four|five|six|seven|eight|nine|ten)\s+(?P<u2>days?|weeks?)"
          r"\s+from\s+(?:now|today))\b")
def _in_n(m, today, anchor):
    text = m.group(0)
    if "fortnight" in text and not m["n"]:
        return _Point(day=today + timedelta(days=14))
    if m["n"] or m["n2"]:
        n = _count(m["n"] or m["n2"])
        unit = m["u"] or m["u2"]
        per = {"day": 1, "week": 7, "fortnight": 14}[unit.rstrip("s")]
        return _Point(day=today + timedelta(days=n * per))
    return _Point(day=today + timedelta(days=7))


@_pattern(r"\ba\s+week\s+from\s+tomorrow\b")
def _week_from_tomorrow(m, today, anchor):
    return _Point(day=today + timedelta(days=8))


@_pattern(rf"\b(?:(?P<q>this\s+coming|this|coming|upcoming|next|on|the)\s+)?(?P<wd>{_WEEKDAY_RE})"
          rf"(?P<after>\s+(?:after\s+next|week|fortnight))?(?:\s+(?:night|evening|arvo|morning))?\b")
def _weekday(m, today, anchor):
    wd = _weekday_index(m["wd"])
    q = (m["q"] or "").replace("this coming", "coming").strip()
    if m["after"]:
        base = _upcoming(today, wd, include_today=False)
        if "fortnight" in m["after"]:
            return _Point(day=base + timedelta(days=14), kind="weekday")
        if "after next" in m["after"] and base - today < timedelta(days=7 - today.weekday()):
            # "Friday after next" said on a Wednesday: the Friday after this
            # one to some, after next week's to others.
            return _Point(day=base + timedelta(days=7), alternative=base + timedelta(days=14), kind="weekday")
        return _Point(day=base + timedelta(days=7), kind="weekday")  # "Friday week"
    if q == "next":
        this_one = _upcoming(today, wd, include_today=True)
        if wd == today.weekday():
            return _Point(day=this_one + timedelta(days=7), kind="weekday")
        # Said on a Wednesday, "next Friday" is this Friday to some people and
        # the one after to others. Default to the week after (the old rule and
        # the prompt's), and carry the other so the agent confirms.
        return _Point(day=this_one + timedelta(days=7), alternative=this_one, kind="weekday")
    if q in ("this", "coming", "upcoming"):
        return _Point(day=_upcoming(today, wd, include_today=True), kind="weekday")
    # Bare "Friday" / "on Friday": the coming one. Said on a Friday it could be
    # tonight or a week away.
    if wd == today.weekday():
        return _Point(day=today, alternative=today + timedelta(days=7), kind="weekday")
    return _Point(day=_upcoming(today, wd, include_today=False), kind="weekday")


@_pattern(rf"\ba\s+week\s+on\s+(?P<wd>{_WEEKDAY_RE})\b")
def _week_on(m, today, anchor):
    wd = _weekday_index(m["wd"])
    base = _upcoming(today, wd, include_today=False)
    if wd == today.weekday():   # said on that day: a week today, or a week after next?
        return _Point(day=today + timedelta(days=7), alternative=base + timedelta(days=7), kind="weekday")
    return _Point(day=base + timedelta(days=7), kind="weekday")


@_pattern(rf"\b(?:on\s+)?the\s+(?P<wd>{_WEEKDAY_RE})\s+after\b(?!\s+next)")
def _weekday_after(m, today, anchor):
    # "the Friday after" — after something said earlier; only the booking is known.
    if anchor is None:
        return _VETO
    return _Point(day=_upcoming(anchor, _weekday_index(m["wd"]), include_today=False), kind="weekday")


@_pattern(rf"\b(?:on\s+)?(?:the\s+)?(?P<wd>{_WEEKDAY_RE})\s+(?:of\s+)?(?P<q>this|next)\s+week\b(?!end)"
          rf"|\b(?P<q2>this|next)\s+week\s+(?:on\s+)?(?:the\s+)?(?P<wd2>{_WEEKDAY_RE})\b")
def _weekday_of_week(m, today, anchor):
    wd = _weekday_index(m["wd"] or m["wd2"])
    monday = today - timedelta(days=today.weekday())
    if (m["q"] or m["q2"]) == "next":
        monday += timedelta(days=7)
    d = monday + timedelta(days=wd)
    if d < today:
        return _Point(conflict=f"{WEEKDAYS[wd].title()} this week has already passed")
    return _Point(day=d, kind="weekday")


@_pattern(rf"\bthe\s+(?P<n>1st|2nd|3rd|4th|last)\s+weekend\s+(?:of|in)\s+(?:the\s+)?"
          rf"(?P<which>this\s+month|next\s+month|month|{_MONTH_WITH_MAY_RE})\b")
def _nth_weekend_of_month(m, today, anchor):
    y, mo = _month_named(m["which"], today)
    saturdays = [date(y, mo, d) for d in range(1, calendar.monthrange(y, mo)[1] + 1)
                 if date(y, mo, d).weekday() == 5]
    n = m["n"]
    sat = saturdays[-1] if n == "last" else saturdays[int(n[0]) - 1] if int(n[0]) <= len(saturdays) else None
    if sat is None or sat < today:
        return None
    return _Point(day=sat, weekend=True)


@_pattern(rf"\b(?:the\s+)?(?P<n>1st|2nd|3rd|4th|last)\s+(?P<wd>{_WEEKDAY_RE})\s+(?:of|in)\s+(?:the\s+)?"
          rf"(?P<which>this\s+month|next\s+month|month|{_MONTH_WITH_MAY_RE})\b")
def _nth_weekday_of_month(m, today, anchor):
    y, mo = _month_named(m["which"], today)
    wd = _weekday_index(m["wd"])
    days = [date(y, mo, d) for d in range(1, calendar.monthrange(y, mo)[1] + 1) if date(y, mo, d).weekday() == wd]
    n = m["n"]
    d = days[-1] if n == "last" else (days[int(n[0]) - 1] if int(n[0]) <= len(days) else None)
    if d is None or d < today:
        return None
    return _Point(day=d, kind="dated")


@_pattern(r"\b(?:the\s+)?weekend\s+after\s+next\b")
def _weekend_after_next(m, today, anchor):
    sat = _this_saturday(today)
    if today.weekday() in (4, 5):   # Fri/Sat: "next weekend" is unambiguous, this is the one after
        return _Point(day=sat + timedelta(days=14), weekend=True)
    return _Point(day=sat + timedelta(days=14), alternative=sat + timedelta(days=7), weekend=True)


@_pattern(r"\b(?:the\s+)?weekend\s+after(?!\s+next)\b")
def _weekend_after(m, today, anchor):
    # "Can I move it to the weekend after?" — after the booking being talked about.
    if anchor is None:
        return _VETO
    return _Point(day=_saturday_of(anchor) + timedelta(days=7), weekend=True)


@_pattern(r"\b(?P<q>this\s+coming|this|the|coming|upcoming|next|over\s+the)\s+weekend\b(?!\s+after)")
def _weekend(m, today, anchor):
    q = m["q"]
    sat = _this_saturday(today)
    if q != "next":
        return _Point(day=sat, weekend=True)
    if today.weekday() in (4, 5):   # said on a Friday or Saturday: clearly the following one
        return _Point(day=sat + timedelta(days=7), weekend=True)
    return _Point(day=sat + timedelta(days=7), alternative=sat, weekend=True)


@_pattern(r"\b(?P<q>this|next|the)\s+week(?P<after>\s+after(?:\s+next)?)?\b(?!end|\s+(?:on|from))")
def _week(m, today, anchor):
    monday = today - timedelta(days=today.weekday())
    q, after = m["q"], (m["after"] or "").strip()
    if after == "after next":
        start = monday + timedelta(days=14)
    elif after == "after":
        if anchor is None:
            return None
        start = anchor - timedelta(days=anchor.weekday()) + timedelta(days=7)
    elif q == "next":
        start = monday + timedelta(days=7)
    elif q == "this":
        return _Point(span=(today, monday + timedelta(days=6)))
    else:
        return None  # "the week" alone is a length, not a date
    return _Point(span=(start, start + timedelta(days=6)))


@_pattern(rf"\b(?P<part>early|mid|middle\s+of|late|start\s+of|beginning\s+of|end\s+of|the\s+end\s+of)\s+"
          rf"(?:the\s+)?(?P<which>this\s+month|next\s+month|month|{_MONTH_WITH_MAY_RE})\b")
def _part_of_month(m, today, anchor):
    y, mo = _month_named(m["which"], today)
    last = calendar.monthrange(y, mo)[1]
    part = m["part"].replace("the ", "")
    lo, hi = {"early": (1, 10), "start of": (1, 7), "beginning of": (1, 7),
              "mid": (11, 20), "middle of": (11, 20), "late": (21, last), "end of": (last - 6, last)}[part]
    start, end = date(y, mo, lo), date(y, mo, hi)
    if end < today:
        return None
    return _Point(span=(max(start, today), end))


@_pattern(rf"\b(?P<which>next\s+month|(?:in|during)\s+{_MONTH_RE})\b")
def _whole_month(m, today, anchor):
    which = re.sub(r"^(?:in|during)\s+", "", m["which"])
    y, mo = _month_named(which, today)
    start, end = date(y, mo, 1), _month_end(y, mo)
    return _Point(span=(max(start, today), end))


def _month_named(which: str, today: date) -> tuple:
    which = which.strip()
    if which in ("this month", "month"):
        return today.year, today.month
    if which == "next month":
        return _add_months(today, 1)
    mo = _month_index(which)
    y = today.year if mo >= today.month else today.year + 1
    return y, mo


_HOLIDAY_RE = re.compile(r"\b(?:" + "|".join(f"(?:{p})" for p in _HOLIDAYS) + r")\b")


_HOLIDAY_SEASON_BEFORE = re.compile(r"\b(?:over|around|during|between|across)\s+(?:the\s+)?$")
_SEASON_WORDS_BEFORE = re.compile(r"\b(?:over|around|during|between|across|after|before|until|till|for)\s+(?:the\s+)?$")
_HOLIDAY_SEASON_AFTER = re.compile(r"^\s*(?:long\s+)?(?:weekend|break|period|holidays?|week|time|party|function)\b")
_HOLIDAY_JOINED_AFTER = re.compile(r"^\s*(?:and|to)\b")
# Named DAYS ("Christmas Day", "Boxing Day", "New Year's Eve"): a check-in day,
# and either end of a range. Bare names ("Christmas", "Easter", "New Year's")
# are seasons as often as days.
_HOLIDAY_DAY_NAME = re.compile(r".*(?:\bday|\beve|good friday|easter (?:saturday|sunday|monday)|melbourne cup)$")


def _holidays(text, today):
    """A holiday named as a day ("Christmas Day", "we'd arrive on Boxing Day").
    "Over Christmas", "Melbourne Cup weekend", "between Christmas and New Year"
    name a season: claimed so no part of them is misread, and not read."""
    out = []
    for m in _HOLIDAY_RE.finditer(text):
        name, before, after = m.group(0), text[:m.start()], text[m.end():]
        if _HOLIDAY_DAY_NAME.match(name):
            season = _HOLIDAY_SEASON_BEFORE.search(before) or _HOLIDAY_SEASON_AFTER.match(after)
        else:
            season = (_SEASON_WORDS_BEFORE.search(before) or _HOLIDAY_SEASON_AFTER.match(after)
                      or _HOLIDAY_JOINED_AFTER.match(after) or re.fullmatch(r"new year'?s|easter(?: weekend)?", name))
        if season:
            out.append((m.start(), m.end(), _VETO))
            continue
        for pattern, fn in _HOLIDAYS.items():
            if re.fullmatch(pattern, name):
                out.append((m.start(), m.end(), _Point(day=_next_holiday(today, fn))))
                break
    return out


_DURATION_RE = re.compile(
    rf"\b(?:for\s+)?(?:just\s+)?(?P<n>{_COUNT_RE}|a\s+couple(?:\s+of)?|couple\s+of)\s+nights?\b"
    r"|\b(?P<one>overnight|(?:just\s+)?the\s+(?:one\s+)?night|a\s+night)\b"
    r"|\bfor\s+(?:a|one|the)\s+week\b|\bfor\s+a\s+fortnight\b|\bfor\s+(?P<w>two|2|three|3)\s+weeks\b")

_PAST_RE = re.compile(
    r"\b(?:last\s+(?:night|weekend|week|month|year|" + "|".join(WEEKDAYS) + r")\b(?!\s+(?:of|in)\b)"
    r"|(?:we|i)\s+(?:stayed|were\s+there|was\s+there|checked\s+out)|ago\b|yesterday)")

_RANGE_JOIN_RE = re.compile(r"^\s*(?:-|to|till|til|until|through|thru|and\s+(?:leave|leaving|out|checking\s+out)"
                            r"|(?:and\s+)?check(?:ing)?\s+out(?:\s+on)?|out\s+on|leaving(?:\s+on)?)\s*(?:on\s+)?(?:the\s+)?$")


def _duration(text: str) -> Optional[int]:
    found = None
    for m in _DURATION_RE.finditer(text):
        s = m.group(0)
        if m["one"]:
            n = 1
        elif "fortnight" in s:
            n = 14
        elif m["w"]:
            n = 7 * _count(m["w"])
        elif "week" in s:
            n = 7
        else:
            raw = m["n"].strip()
            n = 2 if "couple" in raw else _count(raw)
        if found is not None and n != found:
            return None  # two different lengths said: not ours to pick
        found = n
    return found


def _find_points(text: str, today: date, anchor: Optional[date]) -> list:
    hits = []
    for regex, fn in _PATTERNS:
        for m in regex.finditer(text):
            point = fn(m, today, anchor)
            if point is not None:
                hits.append((m.start(), m.end(), point))
    hits += _holidays(text, today)
    # Longest first, then drop anything inside an earlier hit: "Friday the 17th
    # of October" is one date, not three.
    hits.sort(key=lambda h: (-(h[1] - h[0]), h[0]))
    kept = []
    for h in hits:
        if all(h[1] <= k[0] or h[0] >= k[1] for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda h: h[0])


def read_dates(text: str, today: date, anchor: Optional[date] = None) -> Optional[DateReading]:
    """
    What `text` says about a stay, or None when it says nothing reliable.

    `anchor` is the check-in of the booking under discussion, so "the weekend
    after" can mean the weekend after THAT booking.
    """
    t = _normalise(text)
    if not t:
        return None
    nights = _duration(t)
    # Durations are lengths, not dates: blank them so "for a week" is not "in a week".
    scrubbed = _DURATION_RE.sub(lambda m: " " * len(m.group(0)), t)
    points = _find_points(scrubbed, today, anchor)
    phrase = " … ".join(t[s:e] for s, e, _ in points)

    if _PAST_RE.search(t):
        return DateReading(phrase=phrase or t, past=True)
    if any(p.kind == "veto" for _, _, p in points):
        return None
    # A day number nobody read ("24th-26th" with the month somewhere odd) means
    # this is a date we only half understood. Half a date is worse than none.
    for o in re.finditer(r"\b\d{1,2}(?:st|nd|rd|th)\b", scrubbed):
        # (_NOT_A_DATE_AFTER is a negative lookahead: it MATCHES when the next
        # word is not one of "floor", "available", "time"... — i.e. when this
        # number reads as a date.)
        if not any(s <= o.start() and o.end() <= e for s, e, _ in points) and \
                re.match(_NOT_A_DATE_AFTER, scrubbed[o.end():]):
            return None
    if not points:
        return DateReading(nights=nights) if nights else None

    if len(points) == 2:
        (s1, e1, p1), (s2, e2, p2) = points
        # "No, not this weekend — next weekend": a correction. The second one
        # is what they mean, and the dash is not a range.
        negated_first = re.search(r"\bnot\s+(?:the\s+|this\s+|that\s+)?$", scrubbed[max(0, s1 - 12):s1])
        if negated_first:
            join = scrubbed[e1:s2].strip()
            a_range = _RANGE_JOIN_RE.match(scrubbed[e1:s2]) and (
                join != "-" or (p1.kind in ("dom", "dated") and p2.kind in ("dom", "dated")))
            if re.search(r"\bif\b", scrubbed[:s1]) or a_range:
                return None   # "if not Friday then Saturday", "we're not coming Friday to Sunday"
            if not re.search(r"\bnot\b", scrubbed[e1:s2]):
                points = [points[1]]
                phrase = t[s2:e2]
    if len(points) == 2:
        (s1, e1, p1), (s2, e2, p2) = points
        join = scrubbed[e1:s2].strip()
        numeric = p1.kind in ("dom", "dated") and p2.kind in ("dom", "dated")
        if (_RANGE_JOIN_RE.match(scrubbed[e1:s2]) and p1.day and p2.day and not (p1.span or p2.span)
                and (join != "-" or numeric)):
            if p1.conflict or p2.conflict:
                return DateReading(phrase=phrase, conflict=p1.conflict or p2.conflict,
                                   check_in=p1.day, alternative=p1.alternative)
            end = p2.day
            while end <= p1.day:  # "Friday to Sunday" said on a Saturday, "the 30th to the 2nd"
                end = _roll_forward(end, p2)
                if end is None:
                    return None
            return DateReading(phrase=phrase, check_in=p1.day, check_out=end,
                               alternative=p1.alternative, nights=(end - p1.day).days)
        return None  # two unconnected dates: a passing mention, not a range
    if len(points) > 2:
        return None

    _, _, p = points[0]
    if p.conflict:
        return DateReading(phrase=phrase, check_in=p.day, alternative=p.alternative, conflict=p.conflict)
    if p.span:
        return DateReading(phrase=phrase, span=p.span, nights=nights)
    day, alternative = p.day, p.alternative
    if p.weekend and nights == 2:
        # "this weekend, two nights": Friday and Saturday nights.
        day = day - timedelta(days=1)
        alternative = alternative - timedelta(days=1) if alternative else None
    check_out = day + timedelta(days=nights) if nights else None
    if p.weekend and not nights:
        check_out = day + timedelta(days=1)  # AU motel convention: Saturday in, Sunday out
    return DateReading(phrase=phrase, check_in=day, check_out=check_out, alternative=alternative,
                       nights=nights, weekend=p.weekend)


def _roll_forward(end: date, point: _Point) -> Optional[date]:
    """The end of a range that came out before its start: "Friday to Sunday"
    said on a Saturday, "the 30th to the 2nd". A weekday moves a week, a day of
    the month moves a month; anything more specific is left alone."""
    if point.kind == "weekday":
        return end + timedelta(days=7)
    if point.kind == "dom":
        return _next_month_same_day(end)
    return None


def _next_month_same_day(d: date) -> Optional[date]:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    try:
        return date(y, m, d.day)
    except ValueError:
        return None


# ── checking the model's dates against the caller's words ────────────────────

_STAY_CUE = re.compile(
    r"\b(?:stay|staying|book|booking|room|rooms|check(?:ing)?[\s-]?in|arriv\w*|night|nights|available"
    r"|availability|vacanc\w*|come|coming|move|change|instead|switch|swap|push|bring|shift|want|wanted"
    r"|looking|like|need|from|until|till|weekend|week|fortnight)\b")
_OTHER_TOPIC = re.compile(
    r"\b(?:breakfast|pool|wifi|wi-fi|parking|park|pet|pets|dog|dogs|restaurant|open|opens|close|closes"
    r"|weather|reception|office|checkout|what\s+time|laundry|bbq|barbecue|cot|towels?"
    r"|pay|paying|payment|card|call|calling|ring|email|text|phone|link)\b")
# Words that say the dates themselves are being changed.
_CHANGE_CUE = re.compile(r"\b(?:instead|change|changed|move|moved|actually|rather|not|switch|make\s+it|different|meant)\b"
                         r"|^(?:no|nah|nope|wait|hang\s+on|hold\s+on|sorry|oops|hmm|um|uh)\b")
_AGREE_LEAD = re.compile(r"^(?:yes|yeah|yep|yup|sure|ok|okay|right|correct|perfect|great)\b[\s,]*")


def about_the_stay(utterance: str, for_booking: bool = False) -> bool:
    """
    Whether the caller's words are about WHEN they are staying.

    "Is breakfast included tomorrow?" names a day and is not about the stay.
    The checker below only overrides the model when the words carry a stay cue,
    or are a short answer ("next Friday", "the weekend after") with no other
    topic in them — the shape of a reply to "when would you like to come?".
    """
    t = _normalise(utterance)
    if _OTHER_TOPIC.search(t) and not re.search(
            r"\b(?:stay|book|room|night|move|change|instead|check(?:ing)?[\s-]?in)\b", t):
        return False
    if for_booking:
        # At the moment of booking the caller is answering a read-back summary:
        # "yes, this weekend is perfect" restates, it does not change anything.
        # Only words that CHANGE the dates may stop the booking — or a bare
        # date as the whole answer ("yeah, the 24th"), which is the caller
        # naming the dates they mean.
        rest = _AGREE_LEAD.sub("", t)
        return bool(_CHANGE_CUE.search(t)) or len(rest.split()) <= 3
    return bool(_STAY_CUE.search(t)) or len(t.split()) <= 6

def spoken(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()].title()} the {d.day}{_suffix(d.day)} of {MONTHS[d.month - 1].title()}"


def spoken_short(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()].title()} the {d.day}{_suffix(d.day)}"


@dataclass(frozen=True)
class Reconciled:
    check_in: Optional[date]
    check_out: Optional[date]
    # Said before the tool's own answer, so the caller hears which dates were used.
    say_first: str = ""
    # Asked INSTEAD of answering: the dates are not settled.
    ask: str = ""
    changed: bool = False
    reading: Optional[DateReading] = None


def reconcile(model_in: Optional[date], model_out: Optional[date], utterance: str,
              today: date, anchor: Optional[date] = None, for_booking: bool = False) -> Reconciled:
    """
    The dates to use, given what the model sent and what the caller just said.

    The caller's words win when they are unambiguous, because the model's
    arithmetic is the thing being checked. When the caller's phrase has two
    readings, the model's choice stands if it is one of them, and the caller
    hears which. When the words contradict themselves or name only a period,
    the caller is asked.
    """
    r = read_dates(utterance, today, anchor)
    keep = Reconciled(model_in, model_out, reading=r)
    if r is None or r.past:
        return keep
    if not about_the_stay(utterance, for_booking=for_booking):
        if not (for_booking and (r.check_out or r.nights) and about_the_stay(utterance)):
            return keep   # a range or a length at booking time is still checked

    if r.weekend and r.check_in and model_in and model_out and \
            (not r.nights or r.nights == (model_out - model_in).days):
        # "this weekend" covers Friday-to-Sunday as much as Saturday-to-Sunday.
        # The model's stay stands if it starts that Friday or Saturday and
        # includes the Saturday night.
        for cand in (r.check_in, r.alternative):
            if cand is None:
                continue
            sat = cand + timedelta(days=(5 - cand.weekday()) % 7)
            if sat - timedelta(days=1) <= model_in <= sat < model_out:
                other = r.alternative if cand == r.check_in else r.check_in
                say = (f"Just so we're on the same page, that's {spoken_short(model_in)}, "
                       f"not {spoken_short(other)}.") if other else ""
                return Reconciled(model_in, model_out, say_first=say, reading=r)

    if r.conflict:
        if r.alternative:
            return Reconciled(model_in, model_out, reading=r, ask=(
                f"Just to check — {r.conflict}. Did you mean {spoken_short(r.alternative)}, "
                f"or {spoken_short(r.check_in)}?"))
        return Reconciled(model_in, model_out, reading=r, ask=f"Just to check — {r.conflict}. Which date did you mean?")

    if r.span:
        lo, hi = r.span
        if model_in and lo <= model_in <= hi:
            return Reconciled(model_in, model_out, reading=r, say_first=f"That's {spoken_short(model_in)}.")
        return Reconciled(model_in, model_out, reading=r, ask=(
            f"Sure — {spoken_short(lo)} to {spoken_short(hi)}. Which day were you thinking of checking in?"
            if hi > lo else f"Sure — that's {spoken_short(lo)}. Is that right?"))

    if r.check_in is None:  # a length on its own: "two nights"
        if r.nights and model_in and model_out and (model_out - model_in).days != r.nights:
            new_out = model_in + timedelta(days=r.nights)
            return Reconciled(model_in, new_out, reading=r, changed=True)
        return keep

    if r.ambiguous and model_in in (r.check_in, r.alternative):
        chosen = model_in
    else:
        chosen = r.check_in
    other = r.alternative if chosen == r.check_in else r.check_in

    if r.check_out and chosen == r.check_in:
        out = r.check_out
    elif r.nights:
        out = chosen + timedelta(days=r.nights)
    elif model_in and model_out and model_out > model_in:
        out = chosen + (model_out - model_in)
    else:
        out = chosen + timedelta(days=1)

    say = ""
    if r.ambiguous:
        say = f"Just so we're on the same page, that's {spoken_short(chosen)}, not {spoken_short(other)}."
    elif model_in != chosen:
        say = f"That's {spoken_short(chosen)}."
    return Reconciled(chosen, out, say_first=say,
                      changed=(chosen != model_in or out != model_out), reading=r)
