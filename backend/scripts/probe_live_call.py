"""
scripts/probe_live_call.py — what did the last real phone call actually do?

The replay harness settles everything a transcript can settle. It cannot tell
you how the recogniser mangles a spelled-out email over a carrier, what the
model does with "next weekend" when nobody has pre-resolved it, or whether a
gate fires on the real path. Those need a ring, and after the ring you need to
read the evidence rather than remember the call.

Three sources, because no one of them is enough:

  Heroku logs   which gates fired, which tools ran, how a date was resolved,
                whether anything unsourced was spoken
  Appwrite      what was actually written — the row is the truth about the
                booking, whatever the agent said about it
  your ears     what the agent SAID. Nothing logs the spoken text, so the
                checks that depend on it are printed for you to confirm.

Usage (from backend/, venv active):

    python -m scripts.probe_live_call                 # the most recent call
    python -m scripts.probe_live_call --sid CAxxxxx   # a specific call
    python -m scripts.probe_live_call --lines 3000    # look further back
    python -m scripts.probe_live_call --cleanup CC-90001   # delete a test booking

It never writes anything except with --cleanup, which asks first.
"""

import argparse
import asyncio
import os
import re
import subprocess
import sys
from collections import OrderedDict

APP = os.getenv("HEROKU_APP", "ovela")

# Markers the running system already emits. Nothing was added for this probe:
# a check that needs new logging is a check that will rot the moment the
# logging is tidied up.
MARK = {
    "call_start":   re.compile(r"CallSid[=:\s\"']+(CA[0-9a-f]{32})", re.IGNORECASE),
    "tool":         re.compile(r"🔧 \[CascadedOrchestrator\] Tool call: (\w+)\("),
    "gate":         re.compile(r"🔒 \[CascadedOrchestrator\] (\w+) refused"),
    "privacy":      re.compile(r"🔒 Privacy boundary: (\w+) refused"),
    "unsourced":    re.compile(r"🧾 \[CascadedOrchestrator\] unsourced (\w+) spoken: (\S+)"),
    "date_source":  re.compile(r"📅 Booking date resolved: source=(\w+), check_in=(\S+), check_out=(\S+)"),
    "skip_recheck": re.compile(r"♻️ PMS booking: skipping re-check"),
    "room_assign":  re.compile(r"✅ PMS Mode: Auto-assigned room (\S+) to (CC-\d+)"),
    "prefetch_miss": re.compile(r"📇 Caller reservation prefetch missed"),
    "n1_gate":      re.compile(r"N1 gate: create_booking_request called WITHOUT"),
    "transfer":     re.compile(r"transfer", re.IGNORECASE),
}

GREEN, RED, YELLOW, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def fetch_logs(lines: int) -> list:
    try:
        out = subprocess.run(
            ["heroku", "logs", "-n", str(lines), "--app", APP],
            capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        sys.exit("heroku CLI not found. brew install heroku/brew/heroku")
    except subprocess.TimeoutExpired:
        sys.exit("heroku logs timed out")
    if out.returncode != 0:
        sys.exit(f"heroku logs failed: {out.stderr.strip()[:300]}")
    return out.stdout.splitlines()


def split_by_call(lines: list) -> OrderedDict:
    """Group log lines by CallSid. Lines before the first CallSid of a call
    still belong to it — the sid usually appears a beat after the socket
    opens — so the grouping is 'from this sid until the next one'."""
    calls, current = OrderedDict(), None
    pending = []
    for line in lines:
        found = MARK["call_start"].search(line)
        if found:
            sid = found.group(1)
            if sid != current:
                current = sid
                calls.setdefault(sid, [])
                calls[sid].extend(pending)
                pending = []
        if current:
            calls[current].append(line)
        else:
            pending.append(line)
            if len(pending) > 400:
                pending = pending[-400:]
    return calls


def find_all(lines, key):
    return [m for line in lines for m in [MARK[key].search(line)] if m]


def report(sid, lines):
    print(f"\n\033[1mcall {sid}\033[0m   {len(lines)} log lines")
    print("─" * 72)

    tools = [m.group(1) for m in find_all(lines, "tool")]
    if tools:
        counted = OrderedDict()
        for t in tools:
            counted[t] = counted.get(t, 0) + 1
        print("  tools run      " + ", ".join(f"{k}x{v}" if v > 1 else k
                                              for k, v in counted.items()))
    else:
        print(f"  {YELLOW}no tool calls seen — the agent answered from the prompt alone{OFF}")

    checks = []

    # ── D9: the race I closed. This line must never appear again. ──────────
    if find_all(lines, "skip_recheck"):
        checks.append((RED, "FAIL", "availability re-check was SKIPPED before writing a booking "
                                    "— the memo reached the write path again"))
    else:
        checks.append((GREEN, "ok", "no booking skipped its availability re-check"))

    # ── D4: the booking gate. Either it refused, or it let a real one through.
    gates = [m.group(1) for m in find_all(lines, "gate")]
    if gates:
        checks.append((GREEN, "ok", f"gate refused in code: {', '.join(sorted(set(gates)))} "
                                    "— the model was stopped, not asked nicely"))
    privacy = [m.group(1) for m in find_all(lines, "privacy")]
    if privacy:
        checks.append((GREEN, "ok", f"privacy boundary held: {', '.join(sorted(set(privacy)))}"))
    if find_all(lines, "n1_gate"):
        checks.append((YELLOW, "note", "the booking summary gate rejected an attempt — expected "
                                       "if you tried to rush it, a defect if you had confirmed"))

    # ── A3: anything spoken that traced to no source ───────────────────────
    unsourced = [(m.group(1), m.group(2)) for m in find_all(lines, "unsourced")]
    if unsourced:
        for kind, claim in unsourced:
            colour = RED if kind == "reference" else YELLOW
            checks.append((colour, "FLAG", f"unsourced {kind} spoken: {claim}"))
    else:
        checks.append((GREEN, "ok", "nothing spoken that traced to no tool, no knowledge "
                                    "base entry and nothing you said"))

    # ── D11: how the dates were arrived at ─────────────────────────────────
    for m in find_all(lines, "date_source"):
        source, ci, co = m.groups()
        if source == "iso":
            checks.append((YELLOW, "note", f"dates came from the MODEL, unvalidated ({ci} to {co}) "
                                           "— the relative-date resolver did not run"))
        else:
            checks.append((GREEN, "ok", f"dates resolved in code via {source}: {ci} to {co}"))

    for m in find_all(lines, "room_assign"):
        room, ref = m.groups()
        checks.append((YELLOW, "wrote", f"BOOKING CREATED {ref}, room {room} "
                                        f"— free the room with --cleanup {ref}"))

    if find_all(lines, "prefetch_miss"):
        checks.append((YELLOW, "note", "caller-reservation prefetch missed the first turn "
                                       "— first turn was slower than it needed to be"))

    print()
    for colour, tag, text in checks:
        print(f"  {colour}{tag:<5}{OFF} {text}")
    return [m.group(2) for m in find_all(lines, "room_assign")]


def by_ear(refs):
    print("\n\033[1mwhat the logs cannot tell you\033[0m — nothing records the spoken words")
    print("─" * 72)
    for n, q in enumerate([
        "Did it read your EMAIL back before booking, and was it the address you gave?",
        "Did it read the booking summary back — name, dates, room, rate — before asking you to confirm?",
        "When you said \"next weekend\", did it say a date, and was it the RIGHT weekend?",
        "Did it ever state a price, date or reference you had not been told and it had not looked up?",
        "Late in the call, did it still know what was settled at the start?",
        "When something failed, how many things did it try before offering a human?",
    ], 1):
        print(f"  {n}. {q}")
    if refs:
        print(f"\n  {YELLOW}This call wrote {', '.join(refs)} to the live database.{OFF}")


async def cleanup(ref: str):
    """Cancel a test booking so its room goes back on sale.

    Cancelled, not deleted: there is no delete on the data layer and adding one
    is not this script's job. It works because get_motel_reservations() drops
    anything cancelled or rejected BEFORE the availability check sees it, so
    the room is free again the moment the status changes.
    """
    from services.appwrite import db_service
    docs = await db_service.lookup_motel_reservation(booking_reference=ref, tenant_id="coalcreek")
    if not docs:
        print(f"no reservation {ref}")
        return
    doc = docs[0]
    print(f"  {ref}: {doc.get('guest_name')} | {doc.get('check_in_date')} -> "
          f"{doc.get('check_out_date')} | {doc.get('room_type')} | "
          f"status={doc.get('status')} room={doc.get('room_number')}")
    if doc.get("status") == "cancelled":
        print("  already cancelled — the room is already back on sale")
        return
    if input("  cancel it and put the room back on sale? [y/N] ").strip().lower() != "y":
        print("  left alone")
        return
    await db_service.update_motel_reservation(doc["$id"], {"status": "cancelled"})
    print(f"  {GREEN}cancelled {ref} — room {doc.get('room_number')} is sellable again{OFF}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", help="a specific CallSid")
    ap.add_argument("--lines", type=int, default=1500, help="how far back to read")
    ap.add_argument("--all", action="store_true", help="report every call found")
    ap.add_argument("--cleanup", metavar="CC-XXXXX",
                    help="cancel a test booking so its room goes back on sale")
    args = ap.parse_args()

    if args.cleanup:
        asyncio.run(cleanup(args.cleanup))
        return

    calls = split_by_call(fetch_logs(args.lines))
    if not calls:
        sys.exit(f"no CallSid found in the last {args.lines} log lines. "
                 "Ring the number, hang up, then run this again.")

    chosen = list(calls.items())
    if args.sid:
        chosen = [(s, ln) for s, ln in chosen if s == args.sid]
        if not chosen:
            sys.exit(f"no call {args.sid} in the last {args.lines} lines")
    elif not args.all:
        chosen = chosen[-1:]

    refs = []
    for sid, lines in chosen:
        refs += report(sid, lines)
    by_ear(refs)


if __name__ == "__main__":
    main()
