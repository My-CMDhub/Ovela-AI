"""
Normalisation shared by the guest lookup and the per-call memo.

Baseline eval (scripts/eval_identity) before this: recall 40%, and three of the
eighteen misses were not fuzzy-matching problems at all — they were a caller
saying their own number the way Australians say it, and a recogniser inserting
a double space.
"""

import pytest

from services.db.bookings import normalise_lookup_value


class TestNames:
    def test_collapses_internal_whitespace(self):
        # "  Dhruv  Patel " missed in the baseline eval purely for this.
        assert normalise_lookup_value("guest_name", "  Dhruv  Patel ") == "Dhruv Patel"

    def test_title_cases(self):
        assert normalise_lookup_value("guest_name", "dhruv patel") == "Dhruv Patel"

    def test_is_idempotent(self):
        once = normalise_lookup_value("guest_name", "  DHRUV   PATEL  ")
        assert normalise_lookup_value("guest_name", once) == once


class TestPhones:
    @pytest.mark.parametrize("spoken", [
        "0481131771",
        "0481 131 771",
        "+61 481 131 771",
        "(0481) 131-771",
        "61481131771",
    ])
    def test_australian_numbers_reach_one_stored_form(self, spoken):
        assert normalise_lookup_value("phone", spoken) == "+61481131771"

    def test_leaves_an_unrecognised_number_alone_rather_than_mangling_it(self):
        assert normalise_lookup_value("phone", "+1 415 555 0142") == "+14155550142"


class TestReferenceAndEmail:
    def test_reference_upper_cases(self):
        assert normalise_lookup_value("booking_reference", " cc-76818 ") == "CC-76818"

    def test_email_lower_cases(self):
        assert normalise_lookup_value("email", " Dhruv.Patel+Stays@Example.COM ") == "dhruv.patel+stays@example.com"


def test_unknown_field_is_returned_untouched():
    assert normalise_lookup_value("room_type", " Queen ") == " Queen "
