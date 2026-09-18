"""
scripts/seed_reservations.py — realistic reservations for identity-resolution work.

The motel_reservations collection is empty, so every guest lookup on a live call
fails for the most boring reason there is. This seeds a set chosen to make an
identity resolver right or wrong for interesting reasons:

  * names a speech recogniser reliably mangles (Dhruv, Siobhan, Xiuying)
  * two guests sharing a surname, so surname-only matching is not enough
  * two guests whose given names are near-homophones of each other
  * emails that are painful to say out loud (dots, hyphens, digits, plus tags)

Every row carries notes="seed:identity-v1" so it can be removed again.

Usage (from backend/):
    python -m scripts.seed_reservations           # create if absent
    python -m scripts.seed_reservations --purge   # delete the seeded rows
"""

import argparse
import asyncio
import json
from datetime import date, timedelta

from scripts.identity_corpus import GUESTS, TENANT
from services.appwrite import db_service

DB = "6947b8300005f5863f96"
COL = "motel_reservations"
TAG = "seed:identity-v1"

# Anchor for the seeded stays. Keep it ahead of today, or a live test call
# gets told its booking has already passed and proves nothing.
_today = date(2026, 9, 1)


def _d(offset: int) -> str:
    return (_today + timedelta(days=offset)).isoformat()


RATES = {"single": 129.0, "twin": 159.0, "queen": 179.0, "king": 219.0}


def _payload(name, phone, email, room, ref, start, nights):
    return {
        "guest_name": name,
        "guest_phone": phone,
        "guest_email": email,
        "num_guests": 2 if room in ("queen", "king") else 1,
        "room_type": room,
        "check_in_date": _d(start),
        "check_out_date": _d(start + nights),
        "num_nights": nights,
        "status": "confirmed",
        "source": "seed",
        "booking_reference": ref,
        "notes": TAG,
        "tenant_id": TENANT,
        "payment_status": "paid" if nights > 1 else "pending_payment",
        "rate_per_night": RATES[room],
        "total_amount": RATES[room] * nights,
    }


async def _seeded_rows():
    out, offset = [], 0
    while True:
        q = [
            json.dumps({"method": "equal", "attribute": "notes", "values": [TAG]}),
            json.dumps({"method": "limit", "values": [100]}),
            json.dumps({"method": "offset", "values": [offset]}),
        ]
        r = await db_service._make_request(
            "GET", f"/databases/{DB}/collections/{COL}/documents",
            params={f"queries[{i}]": v for i, v in enumerate(q)},
        )
        docs = (r or {}).get("documents", [])
        out.extend(docs)
        if len(docs) < 100:
            return out
        offset += 100


async def purge():
    rows = await _seeded_rows()
    for d in rows:
        await db_service._make_request(
            "DELETE", f"/databases/{DB}/collections/{COL}/documents/{d['$id']}"
        )
    print(f"🧹 removed {len(rows)} seeded reservations")


async def seed():
    existing = {d.get("booking_reference") for d in await _seeded_rows()}
    created = 0
    for g in GUESTS:
        if g[4] in existing:
            continue
        r = await db_service._make_request(
            "POST", f"/databases/{DB}/collections/{COL}/documents",
            data={"documentId": "unique()", "data": _payload(*g)},
        )
        if r:
            created += 1
            print(f"  + {g[0]:20} {g[4]}")
        else:
            print(f"  ! failed: {g[0]}")
    print(f"\n🌱 {created} created, {len(existing)} already present")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--purge", action="store_true", help="delete the seeded rows and exit")
    args = ap.parse_args()
    asyncio.run(purge() if args.purge else seed())


if __name__ == "__main__":
    main()
