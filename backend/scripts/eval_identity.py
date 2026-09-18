"""
scripts/eval_identity.py — how well does guest lookup survive being spoken aloud?

Every query here is the kind of string a speech recogniser actually hands us:
a real guest's details, misheard. The point is to measure two things that pull
against each other.

  RECALL    of the cases where the guest IS in the system, how often do we find
            them? Every miss is a caller asked to repeat themselves.
  PRECISION of the times we returned somebody, how often was it the right
            somebody? Confidently returning the wrong guest is far worse than
            returning nothing, so WRONG-PERSON is reported separately.

The seed data is built to make this hard on purpose: "Drew" is a plausible
mishearing of "Dhruv" AND the surname of a different guest; Katherine Smyth and
Catherine Smith are both real; two Patels share a surname.

Usage (from backend/, after `python -m scripts.seed_reservations`):
    python -m scripts.eval_identity
    python -m scripts.eval_identity --verbose
"""

import argparse
import asyncio

from services.appwrite import db_service

from scripts.identity_corpus import CASES, TENANT


async def _lookup(value: str, field: str):
    kw = {"name": "guest_name", "email": "email", "phone": "phone"}[field]
    docs = await db_service.lookup_motel_reservation(**{kw: value}, tenant_id=TENANT)
    return docs[0].get("booking_reference") if docs else None


async def run(verbose: bool) -> dict:
    tp = fp = fn = wrong = tn = 0
    rows = []
    for spoken, field, expected in CASES:
        try:
            got = await _lookup(spoken, field)
        except Exception as exc:
            got = f"ERROR:{exc}"
        if expected is None:
            if got is None:
                tn += 1
                verdict = "ok (no match)"
            else:
                fp += 1
                verdict = f"FALSE POSITIVE -> {got}"
        else:
            if got == expected:
                tp += 1
                verdict = "ok"
            elif got is None:
                fn += 1
                verdict = "MISS"
            else:
                wrong += 1
                verdict = f"WRONG PERSON -> {got}"
        rows.append((field, spoken, expected, verdict))

    findable = tp + fn + wrong
    returned = tp + wrong + fp
    recall = tp / findable if findable else 0.0
    precision = tp / returned if returned else 0.0

    if verbose:
        for field, spoken, expected, verdict in rows:
            flag = " " if verdict.startswith("ok") else "!"
            print(f" {flag} [{field:5}] {spoken[:44]:46} {str(expected):10} {verdict}")
        print()

    print(f"  recall     {recall:6.1%}   ({tp}/{findable} findable guests located)")
    print(f"  precision  {precision:6.1%}   ({tp}/{returned} answers correct)")
    print(f"  misses         {fn:3}   caller has to repeat themselves")
    print(f"  wrong person   {wrong:3}   worst failure: confident and incorrect")
    print(f"  false pos      {fp:3}   invented a guest who does not exist")
    print(f"  correct nulls  {tn:3}")
    return {"recall": recall, "precision": precision, "misses": fn,
            "wrong_person": wrong, "false_positives": fp}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="print every case")
    args = ap.parse_args()
    asyncio.run(run(args.verbose))


if __name__ == "__main__":
    main()
