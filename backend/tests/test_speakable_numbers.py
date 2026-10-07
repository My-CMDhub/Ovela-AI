"""
tests/test_speakable_numbers.py — prices, times and dates as a caller hears them.

The booking read-back is the sentence the confirmation gate depends on, and
it is mostly numbers. Before this, prepare_for_tts turned "$129.50" into
"129 dollars.50", "$1,200.00" into "1 dollars,200.0th", "2:05 p.m." into
"2:5th p.m." and "2026-09-05" into "2026-9th-5th": a price rule that took only
the leading digits, and a date-ordinal rule applied to every zero-padded number.
"""

import pytest

from services.voice_agent.text_utils import prepare_for_tts


def spoken(text: str) -> str:
    return prepare_for_tts(text)[0]


@pytest.mark.parametrize("text, expected", [
    ("The room is $129.50 per night.", "The room is 129 dollars 50 per night."),
    ("That is $1,200.00 in total.", "That is 1200 dollars in total."),
    ("Total $1,034.05.", "Total 1034 dollars and 5 cents."),
    ("It costs $135 a night.", "It costs 135 dollars a night."),
    ("A $1 deposit", "A 1 dollar deposit"),
    ("a $0.50 fee", "a 50 cents fee"),
    ("$129.5 each", "129 dollars 50 each"),
])
def test_prices_are_read_whole(text, expected):
    assert spoken(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("June 06", "June 6th"),
    ("arriving July 01, 2026", "arriving July 1st, 2026"),
    ("on the 03 of May", "on the 3rd of May"),
    ("from Oct. 02", "from Oct. 2nd"),
    ("2026-09-05", "September 5th, 2026"),
])
def test_zero_padded_days_still_become_ordinals(text, expected):
    assert spoken(text) == expected


@pytest.mark.parametrize("text", [
    "Check-in is at 2:05 p.m.",
    "room 07",
    "Call 0412 345 678.",
    "reference CC-0705",
])
def test_numbers_that_are_not_days_are_left_alone(text):
    assert spoken(text) == text
