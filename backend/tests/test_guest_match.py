"""
Replays every spoken-form query in the identity corpus against an in-memory
roster. No Appwrite, no Twilio, no human on a phone — but the inputs are the
strings a recogniser actually produces, so a regression here is a regression a
caller would hear.

Three failures are graded differently, worst first:

  WRONG PERSON  we read somebody else's booking out loud. Never acceptable.
  FALSE POSITIVE  we invented a guest. Never acceptable.
  MISS          we ask the caller to repeat themselves. Tolerable, measured.

KNOWN_MISSES is the honest list of spoken forms this matcher does not yet
resolve. A name moving out of that list is progress; a name moving into it
must be a deliberate decision, not a silent regression.
"""

import pytest

from scripts.identity_corpus import GUESTS, CASES
from services.db.guest_match import match_by_name, match_by_email

# Mishearings no amount of edit distance can recover: "Drew" and "Through" are
# further from "Dhruv" than unrelated names are from each other, and "Siobhan"
# is spelled nothing like it is said. These need the recogniser's alternative
# hypotheses or a spell-it-out prompt, not a better string metric.
KNOWN_MISSES = {
    "Drew Patel",
    "Through Patel",
    "Shivon O'Connor",
    "Chevonne Oconnor",
}


@pytest.fixture
def roster():
    """The seeded reservations, as the database hands them back."""
    return [
        {"guest_name": name, "guest_email": email, "guest_phone": phone,
         "booking_reference": ref}
        for name, phone, email, _room, ref, _start, _nights in GUESTS
    ]


def _resolve(spoken, field, roster):
    fn = match_by_name if field == "name" else match_by_email
    docs = fn(spoken, roster)
    return docs[0]["booking_reference"] if docs else None


NAME_AND_EMAIL = [c for c in CASES if c[1] in ("name", "email")]


@pytest.mark.parametrize("spoken,field,expected", NAME_AND_EMAIL,
                         ids=[f"{c[1]}:{c[0][:28]}" for c in NAME_AND_EMAIL])
def test_spoken_query_resolves_to_the_right_guest(spoken, field, expected, roster):
    got = _resolve(spoken, field, roster)

    if expected is None:
        assert got is None, f"invented a guest for {spoken!r} -> {got}"
    elif spoken in KNOWN_MISSES:
        # Allowed to fail, never allowed to fail confidently.
        assert got in (None, expected), f"wrong person for {spoken!r} -> {got}"
    else:
        assert got == expected, f"{spoken!r} should resolve to {expected}"


def test_recall_does_not_regress(roster):
    """A floor on the whole corpus, so a change cannot trade recall away quietly."""
    findable = [c for c in NAME_AND_EMAIL if c[2] is not None]
    hits = sum(1 for s, f, e in findable if _resolve(s, f, roster) == e)
    assert hits >= 21, f"recall fell to {hits}/{len(findable)}"


def test_never_returns_the_wrong_guest(roster):
    """The failure that matters most, asserted on its own so it cannot hide."""
    wrong = [(s, e, _resolve(s, f, roster))
             for s, f, e in NAME_AND_EMAIL
             if e is not None and _resolve(s, f, roster) not in (None, e)]
    assert wrong == []


# --- the pieces, tested where they are cheap to reason about -----------------

def test_a_name_spelled_out_reduces_to_the_same_letters_as_the_written_one():
    """Where the word break falls is not recoverable, so it is not relied on."""
    from services.db.guest_match import fold_name
    spelled = fold_name("D H R U V   P A T E L").replace(" ", "")
    written = fold_name("Dhruv Patel").replace(" ", "")
    assert spelled == written == "dhruvpatel"


def test_apostrophes_and_hyphens_do_not_count_against_a_name():
    from services.db.guest_match import fold_name
    assert fold_name("O'Connor") == fold_name("OConnor") == "oconnor"
    assert fold_name("Jean-Luc") == "jean luc"


def test_a_spoken_email_folds_to_the_same_skeleton_as_the_written_one():
    from services.db.guest_match import email_skeleton
    assert (email_skeleton("dhruv patel plus stays at example dot com")
            == email_skeleton("dhruv.patel+stays@example.com"))


# --- a name alone is weak evidence, and sometimes it is no evidence ----------

def test_an_exact_name_does_not_identify_a_guest_another_guest_answers_to(roster):
    """
    Flux transcribes spoken "Katherine Smyth" as "Catherine Smith" at 0.95
    confidence — a different real guest, spelled perfectly. Matching on the
    string alone hands over the wrong booking, so neither name resolves on its
    own any more. Both need a second field.
    """
    assert match_by_name("Catherine Smith", roster) == []
    assert match_by_name("Katherine Smyth", roster) == []


def test_a_shared_surname_alone_still_does_not_identify_anybody(roster):
    assert match_by_name("Patel", roster) == []


def test_an_unrivalled_name_still_resolves(roster):
    """The rule must cost only the genuinely ambiguous cases."""
    assert match_by_name("Priya Patel", roster)[0]["booking_reference"] == "CC-76819"
    assert match_by_name("Bhruv Patel", roster)[0]["booking_reference"] == "CC-76818"
    assert match_by_name("Dhruv", roster)[0]["booking_reference"] == "CC-76818"


def test_a_guest_with_two_bookings_is_one_guest_not_an_ambiguity(roster):
    """
    The rival that blocks a match has to be a different person. Two rows for the
    same guest are two bookings, and both should come back.
    """
    roster = roster + [{"guest_name": "Dhruv Patel", "guest_email": "dhruv.patel+stays@example.com",
                        "guest_phone": "+61481131771", "booking_reference": "CC-99001"}]
    refs = [d["booking_reference"] for d in match_by_name("Dhruv Patel", roster)]
    assert sorted(refs) == ["CC-76818", "CC-99001"]


# --- confirming an identity we already hold, which is a different job --------

def test_name_confirms_accepts_a_misheard_first_name():
    """
    Identity came from the phone number. The spoken name only has to be
    compatible with it, so the bar is far lower than picking a guest from a list.
    """
    from services.db.guest_match import name_confirms
    assert name_confirms("Drew Patel", "Dhruv Patel")
    assert name_confirms("Bhruv Patel", "Dhruv Patel")
    assert name_confirms("Dhruv", "Dhruv Patel")
    assert name_confirms("dhruv patel", "Dhruv Patel")


def test_name_confirms_rejects_a_different_person_on_the_same_phone():
    """A shared line. Nothing about this name is compatible with the booking."""
    from services.db.guest_match import name_confirms
    assert not name_confirms("Sarah Wilkinson", "Dhruv Patel")
    assert not name_confirms("Catherine Smith", "Dhruv Patel")
    assert not name_confirms("", "Dhruv Patel")
    assert not name_confirms("Dhruv Patel", "")
