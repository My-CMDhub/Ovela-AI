"""
tests/test_grounding.py — the check for things the agent said that came from nowhere.

The gates stop the agent DOING what it should not. This is about what it SAYS:
a rate, a date or a booking reference spoken confidently and traceable to no
tool result, no page of the knowledge base and nothing the caller said.

Measured before it is enforced, so these tests pin the CHECK, not a refusal.
A false flag would gag the agent mid-sentence, and the rate has to be known
first — scripts/replay_conversation.py reports it as `unsourced claims`.
"""

from services.voice_agent.grounding import unsourced_claims, business_facts

# What a lookup actually hands back, trimmed to the fields under test.
LOOKUP = ("{'booking_reference': 'CC-76818', 'guest_name': 'Dhruv Patel', "
          "'check_in_date': '2026-09-04', 'check_out_date': '2026-09-06', "
          "'total_amount': 358, 'room_type': 'queen'}")


def kinds(claims):
    return sorted(kind for kind, _ in claims)


class TestNothingIsFlaggedThatHasASource:
    def test_reading_a_tool_result_back_is_clean(self):
        said = ("You're in a queen from the 4th of September to the 6th, "
                "reference CC-76818, and the total is $358.")
        assert unsourced_claims(said, [LOOKUP]) == []

    def test_a_rate_from_the_knowledge_base_is_not_invented(self):
        """Room rates live in the system prompt, not in any tool result. A check
        that flagged them would be measuring its own ignorance."""
        said = "The Double Room is $135 a night."
        assert unsourced_claims(said, [LOOKUP] + business_facts()) == []

    def test_a_date_the_caller_said_first_is_sourced(self):
        """The caller is a source. They named the dates before any tool ran."""
        said = "Let me check the 10th of September for you."
        assert unsourced_claims(said, ["I'd like a room on the 10th of September"]) == []

    def test_the_same_date_written_differently_still_matches(self):
        """The tool answers in ISO, the agent speaks in words. Comparing the
        strings would flag every correct date the agent ever said."""
        assert unsourced_claims("Checking in September 4th.", [LOOKUP]) == []
        assert unsourced_claims("Checking in on the 4th of September.", [LOOKUP]) == []

    def test_a_total_written_with_a_comma_is_the_same_total(self):
        assert unsourced_claims("That comes to $1,240.",
                                ["{'total_amount': 1240}"]) == []

    def test_saying_nothing_numeric_is_clean(self):
        assert unsourced_claims("Of course, let me take a look at that for you.", [LOOKUP]) == []

    def test_no_sources_at_all_does_not_crash(self):
        assert kinds(unsourced_claims("Reference CC-76818.", [])) == ["reference"]
        assert unsourced_claims("", []) == []


class TestTheThingsWorthCatching:
    def test_an_invented_reference(self):
        """The worst of the three. There is no way to say a reference by
        accident, and no way for the caller to check it on the phone."""
        claims = unsourced_claims("Your reference is CC-99999.", [LOOKUP])
        assert claims == [("reference", "CC-99999")]

    def test_an_invented_price(self):
        claims = unsourced_claims("It works out to $412 for the two nights.",
                                  [LOOKUP] + business_facts())
        assert claims == [("money", "$412")]

    def test_an_invented_date(self):
        claims = unsourced_claims("You're checking out on the 19th of September.", [LOOKUP])
        assert claims == [("date", "19/09")]

    def test_a_price_said_in_words_is_still_caught(self):
        claims = unsourced_claims("That'll be 412 dollars.", [LOOKUP] + business_facts())
        assert claims == [("money", "$412")]

    def test_each_kind_is_reported_separately(self):
        """They are not equally serious — an invented reference is a fabricated
        record, an invented date is usually a restatement gone slightly wrong —
        so they are never added into one number."""
        said = "Reference CC-99999, checking in the 19th of September, total $412."
        assert kinds(unsourced_claims(said, [LOOKUP])) == ["date", "money", "reference"]


class TestThePipelineTrap:
    def test_the_check_runs_on_the_model_text_not_the_spoken_text(self):
        """prepare_for_tts rewrites the text before Cartesia sees it, and it
        rewrites dates past recognition: "2026-09-19" becomes "2026-9th-19".
        Point this check at that end of the pipeline and every invented date
        goes quiet — a green light meaning only that the patterns stopped
        matching. (Money happens to survive, "$412" becoming "412 dollars",
        which is worse rather than better: a check that half works is the kind
        you trust.)"""
        from services.voice_agent.text_utils import prepare_for_tts

        model_text = "Your stay starts 2026-09-19."
        spoken_text, _ = prepare_for_tts(model_text)

        assert unsourced_claims(model_text, [LOOKUP]) == [("date", "19/09")]
        assert spoken_text != model_text
        assert unsourced_claims(spoken_text, [LOOKUP]) == []   # the trap, pinned
