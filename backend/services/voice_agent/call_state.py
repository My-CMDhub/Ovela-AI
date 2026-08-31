"""
services/voice_agent/call_state.py — what the call knows, kept outside the model.

Every turn is rebuilt from scratch as [system prompt] + [caller note] +
[transcript]. Tool calls and their results are appended to a *local* message
list inside the turn and thrown away when the turn ends; only the caller's words
and the agent's spoken reply reach `self.history`. So a fact the agent learned
from a tool survives only if it happened to say that fact out loud.

That is the owner's "it loses the past content as the call goes long", and it is
not a context-window problem. Measured on scripts/replay_conversation.py
--only long-call, five runs: the booking reference was looked up on turn 2 and
asked for again on turn 18, and the agent answered "I can't see the reference
here" in 5 runs out of 5. It was telling the truth.

So the system keeps the notes rather than the model. This object watches every
tool result, keeps the handful of fields that are facts about *this* call, and
is re-injected each turn as facts — not as replayed conversation.

Two boundaries it must not cross, both Track A:

* **Nothing is recorded until identity is confirmed in code.** `lookup_booking`
  hands over dates and a reference for an unidentified caller but withholds the
  guest's name; a note that then carried the reservation forward for the rest of
  the call would quietly widen that. Until the tool says the name matched, all
  this holds is "a reservation exists on this number".
* **The guest's email and phone are never carried.** The tool releases those on
  the turn a name matched. Re-sending them in a note on every later turn is a
  bigger surface for no gain — the model can call the tool again, and the
  per-call cache makes that free.
"""

from dataclasses import dataclass, field

# How much of the transcript the model still sees word for word. Older turns are
# dropped rather than summarised: their *facts* are in the note below, and a
# summary of the rest would be one more thing that can be wrong. Twenty messages
# is ten exchanges, which is more recent conversation than a phone call needs.
TRANSCRIPT_WINDOW = 20

# How many recent tool results are kept for the grounding check. Sixty is more
# than a long call produces; the cap only exists so an hour on the line cannot
# grow this without bound.
EVIDENCE_KEPT = 60

# Tools whose success is a promise the business now has to keep. The model may
# be asked "did you already send that?" ten turns later, and "I think so" is the
# wrong answer either way.
_PROMISES = {
    "create_booking_request":       "a booking was created",
    "resend_payment_link":          "the payment link was re-sent",
    "resend_payment_confirmation":  "the payment confirmation was re-sent",
    "request_human_callback":       "a callback from staff was arranged",
    "update_guest_info":            "the guest's details were updated",
    "transfer_to_staff":            "the call was put through to staff",
}


def recent_transcript(history: list) -> list:
    """The tail of the conversation the model still sees verbatim."""
    return history[-TRANSCRIPT_WINDOW:] if len(history) > TRANSCRIPT_WINDOW else list(history)


def _succeeded(result: dict) -> bool:
    return bool(result.get("success") or result.get("found") or result.get("transferred"))


@dataclass
class CallState:
    """Facts established on this call, owned by code rather than by the model."""

    # Identity — set only by a tool that matched a name in Python.
    identity_confirmed: bool = False
    identity_basis: str = ""
    reservation_on_file: bool = False   # true before identity, carries no detail

    # The stay, once identity is confirmed.
    guest_name: str = ""
    booking_reference: str = ""
    room_type: str = ""
    check_in: str = ""
    check_out: str = ""
    num_nights: str = ""
    total_amount: str = ""
    payment_status: str = ""

    # Availability already quoted aloud, so a second answer cannot contradict
    # the first: "<dates>, <room>" -> the verdict that was given.
    availability: dict = field(default_factory=dict)

    # One-way actions that actually completed, in the order they happened.
    promises: list = field(default_factory=list)

    # Raw tool results, kept only so services/voice_agent/grounding.py can ask
    # whether a number the agent said came from anywhere. Never sent to the
    # model — the note above is what the model sees. Bounded so a long call
    # cannot grow it without limit.
    evidence: list = field(default_factory=list)

    def observe(self, tool_name: str, args: dict, result) -> None:
        """Record what a tool result established. Never raises — a bad result
        must not take down the turn that produced it."""
        if not isinstance(result, dict):
            return
        self.evidence.append(str(result))
        del self.evidence[:-EVIDENCE_KEPT]
        try:
            if tool_name == "lookup_booking":
                self._observe_lookup(result)
            elif tool_name == "create_booking_request" and result.get("success"):
                # The caller gave these details themselves this call, so the
                # booking is theirs by construction.
                self._absorb(result, args)
                self.identity_confirmed = True
                self.identity_basis = "they made this booking on this call"
            elif tool_name == "check_availability":
                self._observe_availability(args, result)

            promise = _PROMISES.get(tool_name)
            if promise and _succeeded(result) and promise not in self.promises:
                self.promises.append(promise)
        except Exception:      # pragma: no cover - defensive, see docstring
            pass

    def _observe_lookup(self, result: dict) -> None:
        # A name that did not fit is not evidence about anybody, and must not
        # downgrade an identity already confirmed earlier in the call. A result
        # carrying no reference is not a booking either, whatever `found` says
        # — confirming identity off a half-formed result is how the wrong
        # person gets treated as the guest for the rest of the call.
        if not result.get("found") or not result.get("booking_reference"):
            return
        if result.get("identity_unconfirmed"):
            self.reservation_on_file = True
            return
        self.reservation_on_file = True
        self.identity_confirmed = True
        self.identity_basis = {
            "caller_phone": "the name they gave matched the reservation on this number",
            "reference":    "they gave the booking reference",
            "phone":        "they gave the phone number on the reservation",
            "name":         "the name they gave matched a reservation",
            "email":        "they gave the email on the reservation",
        }.get(result.get("found_by", ""), "a tool matched them to this reservation")
        self._absorb(result, {})

    def _absorb(self, result: dict, args: dict) -> None:
        for attr, key in (
            ("guest_name", "guest_name"), ("booking_reference", "booking_reference"),
            ("room_type", "room_type"), ("check_in", "check_in_date"),
            ("check_out", "check_out_date"), ("num_nights", "num_nights"),
            ("total_amount", "total_amount"), ("payment_status", "payment_status"),
        ):
            value = result.get(key) or args.get(key) or ""
            if value != "" and value is not None:
                setattr(self, attr, str(value))

    def _observe_availability(self, args: dict, result: dict) -> None:
        if not args.get("check_in_date") or not args.get("check_out_date"):
            return      # an answer about no dates is not an answer to hold anyone to
        dates = f"{args['check_in_date']} to {args['check_out_date']}"
        room = args.get("room_type") or "any room"
        available = result.get("available")
        self.availability[f"{dates}, {room}"] = (
            "not checked" if available == "unknown"
            else "available" if available else "nothing free"
        )

    def as_note(self) -> str:
        """The facts, as a system message. Empty while there is nothing to say."""
        lines = []
        if self.identity_confirmed:
            lines.append(f"- Caller identity: CONFIRMED — {self.identity_basis}.")
        elif self.reservation_on_file:
            lines.append(
                "- A reservation exists on this phone number. The caller has NOT "
                "been identified yet, so you have not been told whose it is."
            )

        if self.identity_confirmed and self.booking_reference:
            stay = [f"reference {self.booking_reference}"]
            if self.guest_name:
                stay.append(f"guest {self.guest_name}")
            if self.room_type:
                stay.append(f"{self.room_type} room")
            if self.check_in and self.check_out:
                nights = f" ({self.num_nights} nights)" if self.num_nights else ""
                stay.append(f"{self.check_in} to {self.check_out}{nights}")
            if self.total_amount:
                stay.append(f"total ${self.total_amount}")
            if self.payment_status:
                stay.append(f"payment {self.payment_status}")
            lines.append(f"- Their booking: {', '.join(stay)}.")

        for what, verdict in self.availability.items():
            lines.append(f"- Availability already quoted for {what}: {verdict}.")

        if self.promises:
            lines.append(f"- Already done on this call: {'; '.join(self.promises)}.")

        if not lines:
            return ""
        return (
            "CALL STATE — established earlier in this call and kept for you by the "
            "system, because the tool results that produced them are no longer in "
            "your context. Treat these as things you already know: answer from them "
            "directly rather than saying you cannot see them, and do not contradict "
            "them or look them up again unless the caller says something has "
            "changed.\n" + "\n".join(lines)
        )
