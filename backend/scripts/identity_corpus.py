"""
scripts/identity_corpus.py — the guest roster and the spoken queries, in one place.

Three things read this file and they must never disagree:

  scripts/seed_reservations.py   writes GUESTS into Appwrite
  scripts/eval_identity.py       replays CASES against the live database
  tests/test_guest_match.py      replays CASES against an in-memory roster, offline

The roster is chosen to make an identity resolver right or wrong for interesting
reasons, not to be easy: "Drew" is both a plausible mishearing of "Dhruv" and the
surname of a different guest; Katherine Smyth sits beside Catherine Smith; two
Patels share a surname; several emails are painful to say out loud.
"""

import os

from dotenv import load_dotenv

# Read backend/.env directly: this module is imported by scripts and tests that
# never construct the Settings object, so nothing else has loaded it.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TENANT = "coalcreek"

# The owner tests from a real handset. Its number lives in backend/.env, which is
# gitignored, so it never lands in the repository; the literal below is a
# placeholder for anyone else running the seeder. Keeping these in sync matters:
# a wrong number here silently tests the fallback path instead of the real one,
# which is exactly what happened on the 31 August call.
CALLER_PHONE = os.getenv("SEED_CALLER_PHONE", "+61481131771")

# guest_name, phone, email, room_type, booking_reference, check-in offset, nights
GUESTS = [
    ("Dhruv Patel",        CALLER_PHONE,   "dhruv.patel+stays@example.com",  "queen",  "CC-76818", 3, 2),
    ("Priya Patel",        "+61412998231", "priya_patel91@outlook.com",    "twin",   "CC-76819", 3, 1),
    ("Siobhan O'Connor",   "+61423884190", "s.oconnor-work@bigpond.com",   "king",   "CC-76820", 5, 3),
    ("Xiuying Zhang",      "+61455201773", "xiuying.zhang2@icloud.com",    "queen",  "CC-76821", 1, 2),
    ("Andrew Drew",        "+61466310922", "andrew.drew@hotmail.com",      "single", "CC-76822", 7, 1),
    ("Aaron Aarons",       "+61477452118", "aaron.aarons@gmail.com",       "twin",   "CC-76823", 9, 2),
    ("Mohammed Al-Rashid", "+61488772039", "m.alrashid+motel@proton.me",   "king",   "CC-76824", 2, 4),
    ("Katherine Smyth",    "+61499103846", "kate.smyth@yahoo.com.au",      "queen",  "CC-76825", 4, 1),
    ("Catherine Smith",    "+61401557262", "catherine.smith88@gmail.com",  "queen",  "CC-76826", 4, 2),
    ("Jean-Luc Beaumont",  "+61432119047", "jl.beaumont@orange.fr",        "king",   "CC-76827", 6, 3),
]

# (what the recogniser produced, field, expected booking_reference or None)
#
# `None` means the only correct answer is "I could not find you" — returning a
# guest here is a false positive, which on a phone call means reading somebody
# else's booking out loud.
CASES = [
    # --- exact, as a control -------------------------------------------------
    ("Dhruv Patel",           "name",  "CC-76818"),

    # --- case and spacing, which the recogniser varies freely -----------------
    ("dhruv patel",           "name",  "CC-76818"),
    ("DHRUV PATEL",           "name",  "CC-76818"),
    ("  Dhruv  Patel ",       "name",  "CC-76818"),

    # --- genuine mishearings of Dhruv, observed or plausible -----------------
    ("Drew Patel",            "name",  "CC-76818"),
    ("Bhruv Patel",           "name",  "CC-76818"),
    ("Druv Patel",            "name",  "CC-76818"),
    ("Dhruve Patel",          "name",  "CC-76818"),
    ("Through Patel",         "name",  "CC-76818"),

    # --- other names a recogniser mangles ------------------------------------
    ("Shivon O'Connor",       "name",  "CC-76820"),
    ("Chevonne Oconnor",      "name",  "CC-76820"),
    ("Shuying Zhang",         "name",  "CC-76821"),
    ("Mohamed Alrashid",      "name",  "CC-76824"),
    ("Jean Luc Beaumont",     "name",  "CC-76827"),

    # --- spelled out, letter by letter, as callers do when asked -------------
    ("D H R U V   P A T E L", "name",  "CC-76818"),

    # --- given name only, surname only ---------------------------------------
    ("Dhruv",                 "name",  "CC-76818"),
    ("Beaumont",              "name",  "CC-76827"),

    # --- PRECISION TRAPS: near neighbours that must not be confused ----------
    ("Priya Patel",           "name",  "CC-76819"),   # not Dhruv Patel
    ("Andrew Drew",           "name",  "CC-76822"),   # not Dhruv-misheard-as-Drew
    ("Aaron Aarons",          "name",  "CC-76823"),

    # --- nobody: returning a guest here is a false positive ------------------
    #
    # The Smyth/Smith pair is not an unknown caller — both are real guests. A
    # probe through Cartesia and Flux (scripts/probe_asr_confidence.py) showed
    # spoken "Katherine Smyth" transcribed as "Catherine Smith" at 0.95
    # confidence: a different guest's name, spelled perfectly. Neither can be
    # identified by name alone any more; both need a phone, reference or email.
    ("Katherine Smyth",       "name",  None),
    ("Catherine Smith",       "name",  None),

    ("Gareth Williams",       "name",  None),
    ("Patel",                 "name",  None),         # two Patels; ambiguous
    ("Smith",                 "name",  None),         # Smith and Smyth sound identical
    ("John Smith",            "name",  None),

    # --- emails, said out loud ------------------------------------------------
    ("dhruv.patel+stays@example.com",             "email", "CC-76818"),
    ("dhruv patel plus stays at example dot com", "email", "CC-76818"),
    ("DHRUV.PATEL+STAYS@EXAMPLE.COM",             "email", "CC-76818"),
    ("s.oconnor-work@bigpond.com",              "email", "CC-76820"),
    ("s oconnor dash work at bigpond dot com",  "email", "CC-76820"),
    ("nobody@nowhere.com",                      "email", None),

    # --- phone, with and without country code --------------------------------
    ("+61481131771",          "phone", "CC-76818"),
    ("0481131771",            "phone", "CC-76818"),
    ("0481 131 771",          "phone", "CC-76818"),
    ("+61400000000",          "phone", None),
]
