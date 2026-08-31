"""
services/db/guest_match.py — find the guest a caller just said out loud.

An exact query is right when the recogniser got the name right, and useless the
rest of the time. This is the rung below it: score the tenant's reservations
against what was heard, and answer only when one of them is clearly ahead.

The rule that keeps this safe is the margin, not the threshold. Reading the
wrong guest's booking down the phone is far worse than asking somebody to
repeat themselves, so a contested match returns nothing on purpose.

Pure functions over rows already in memory — no database, no network — so the
whole thing can be replayed offline against the seeded roster.
"""

import logging
import re
import unicodedata
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# A genuine mishearing of a name in this roster scores 0.71–0.94 against the
# true name; two unrelated names score at most 0.50. Every query word has to
# clear this against *some* word of the candidate, so "Patel" cannot drag
# "Andrew Drew" over the line on the strength of "Drew" alone.
TOKEN_FLOOR = 0.70

# How far ahead the winner must be before we will say a name aloud. One spoken
# word is thin evidence — a caller who says "Smith" may well be Smyth — so it
# needs a much wider gap than a full name does.
MARGIN_BY_WORD_COUNT = {1: 0.25}
DEFAULT_MARGIN = 0.10

# Said aloud, these are punctuation. Only ever stripped when they stand alone
# between spaces, so "kate.smyth@..." keeps every letter of "kate".
SPOKEN_PUNCTUATION = {
    "at", "dot", "period", "point", "plus", "dash", "hyphen",
    "underscore", "underscores",
}


def fold_name(value: str) -> str:
    """
    Reduce a name to the part a recogniser can be trusted on: letters and word
    breaks. Accents, apostrophes and hyphens are transcription decisions, not
    facts about the guest — O'Connor, OConnor and o connor are one person.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = stripped.replace("'", "").replace("’", "")
    stripped = re.sub(r"[^0-9A-Za-z]+", " ", stripped)
    return " ".join(stripped.split()).lower()


def email_skeleton(value: str) -> str:
    """
    Reduce an address to its letters and digits, after dropping the words a
    caller says instead of typing punctuation.

        "dhruv patel plus stays at example dot com"  ->  dhruvpatelstaysexamplecom
        "dhruv.patel+stays@example.com"              ->  dhruvpatelstaysexamplecom

    A written address has no spaces, so it passes through the word filter
    untouched; only a spoken one is ever edited.
    """
    if not value:
        return ""
    words = [w for w in value.strip().lower().split()
             if w not in SPOKEN_PUNCTUATION]
    return re.sub(r"[^0-9a-z]+", "", " ".join(words))


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _score(query_words, candidate_words) -> float:
    """
    Mean similarity, but only once every query word has found a home. A word
    that matches nothing means this is a different guest, however well the rest
    of the name lines up.
    """
    if not query_words or not candidate_words:
        return 0.0
    per_word = []
    for q in query_words:
        best = max(_ratio(q, c) for c in candidate_words)
        if best < TOKEN_FLOOR:
            return 0.0
        per_word.append(best)
    return sum(per_word) / len(per_word)


def _decide(scored, margin, spoken):
    """
    Answer only if the winner is clear of the field, and say which it was.

    `scored` is one entry per *guest*, not per row — two reservations under the
    same name are one person with two bookings, and both come back together.
    """
    if not scored:
        logger.info("guest_match: nothing close to %r", spoken)
        return []
    scored.sort(key=lambda pair: -pair[0])
    best_score, best_docs = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0

    # A name identifies a guest only when nobody else answers to it, and an
    # exact match is not exempt from that. Flux transcribes a spoken "Katherine
    # Smyth" as "Catherine Smith" at 0.95 confidence — a different real guest,
    # spelled perfectly — so a string that matches one guest exactly is still
    # not evidence of which of the two is on the line.
    if runner_up >= TOKEN_FLOOR:
        logger.info(
            "guest_match: %r fits more than one guest (%.2f and %.2f) — "
            "a name alone cannot identify them",
            spoken, best_score, runner_up,
        )
        return []

    if best_score - runner_up < margin:
        # Two guests fit what was heard. Saying either one aloud is a coin flip
        # with somebody's booking, so decline and let the caller disambiguate.
        logger.info(
            "guest_match: %r is contested (%.2f vs %.2f, needed +%.2f) — declining",
            spoken, best_score, runner_up, margin,
        )
        return []
    logger.info(
        "guest_match: %r -> %r (%.2f, next %.2f), %d booking(s)",
        spoken, best_docs[0].get("guest_name"), best_score, runner_up, len(best_docs),
    )
    return best_docs


def match_by_name(spoken: str, candidates: list) -> list:
    """The guest whose name best explains what was heard, or nothing."""
    query = fold_name(spoken)
    if not query:
        return []
    query_words = query.split()
    squashed = query.replace(" ", "")

    # Score each distinct guest once, keeping every booking under that name.
    by_guest = {}
    for doc in candidates:
        folded = fold_name(doc.get("guest_name") or "")
        if not folded:
            continue
        if folded not in by_guest:
            # Ignoring word breaks catches both "Jean Luc" for "Jean-Luc" and a
            # caller spelling their name out one letter at a time.
            score = (1.0 if folded.replace(" ", "") == squashed
                     else _score(query_words, folded.split()))
            by_guest[folded] = (score, [])
        by_guest[folded][1].append(doc)

    scored = [(score, docs) for score, docs in by_guest.values() if score]
    margin = MARGIN_BY_WORD_COUNT.get(len(query_words), DEFAULT_MARGIN)
    return _decide(scored, margin, spoken)


def match_by_email(spoken: str, candidates: list) -> list:
    """
    An address matches on its skeleton or not at all. Two guests differing only
    in punctuation would be ambiguous, so that returns nothing rather than a
    coin flip.
    """
    skeleton = email_skeleton(spoken)
    if not skeleton:
        return []
    hits = [doc for doc in candidates
            if email_skeleton(doc.get("guest_email") or "") == skeleton]
    # One address belongs to one guest, so several hits are their several
    # bookings — not an ambiguity. Different names on one address is.
    if len({fold_name(doc.get("guest_name") or "") for doc in hits}) == 1:
        return hits
    return []


def name_confirms(spoken: str, stored: str) -> bool:
    """
    Is the name just spoken compatible with the guest we already identified?

    This is a *confirmation*, not a search, and the difference sets the bar.
    match_by_name picks one guest out of a whole book, so it demands every word
    fit and a clear lead. Here the identity came from the number that dialled —
    something the recogniser never touched — and the only question is whether
    this caller could be that person. One word landing is enough:

        "Drew Patel"      -> Dhruv Patel     surname lands            yes
        "Sarah Wilkinson" -> Dhruv Patel     nothing lands            no

    Being wrong in the lenient direction costs one clarifying question. Being
    wrong in the strict direction sends a real guest away. So it leans lenient.

    ponytail: a relative of the guest sharing their phone ("Priya Patel") also
    lands on the surname and gets asked to confirm the wrong first name. Needs
    the roster to do better, which this path does not have.
    """
    a, b = fold_name(spoken), fold_name(stored)
    if not a or not b:
        return False
    if a == b or a.replace(" ", "") == b.replace(" ", ""):
        return True
    return any(_ratio(x, y) >= TOKEN_FLOOR for x in a.split() for y in b.split())
