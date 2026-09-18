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
* **The guest's phone is never carried; their email is, once identity is
  confirmed.** Both used to be left out on the theory that the model would call
  the tool again when it needed them. On a live call (18 Sep) it did not: two
  turns after the lookup it told the caller no email was on file, then read
  back an address it made up. A caller who has already proven they are the
  guest is safer hearing their real address than an invented one.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# The words that make a run of letters a NAME rather than an email, a booking
# reference or a street. Matched against the agent's question as well as the
# caller's answer, because the cue usually sits in the question.
_SPELLING_A_NAME = re.compile(
    r"\b(name|names|spell|spelt|spelled|spelling|surname|initial|initials|"
    r"first|last|given|family)\b", re.IGNORECASE)

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
    guest_email: str = ""

    # What the CALLER gave us that no tool has confirmed. For a stranger with
    # no record these are the only copy in existence: update_guest_info used to
    # answer "Details safely stored in my temporary memory for this call" and
    # store nothing at all, so the transcript was their only home — and the
    # transcript is capped at TRANSCRIPT_WINDOW. Measured on
    # replay_conversation --only new-caller-long: spelled out on turn 3, asked
    # for on turn 17, lost 3 runs out of 3, once replaced with a different real
    # guest's name lifted from a worked example in the system prompt.
    heard_name: str = ""
    heard_email: str = ""
    # What the caller SPELLED, letter by letter. Kept apart from heard_name
    # because it is better evidence: a caller who spells their name is telling
    # you they expect the sound to be wrong. On a real call the recogniser got
    # every letter of "s i o b h a n" right and the booking was still written
    # as "Cyborn O'Connor", because nothing read the letters.
    spelled_name: str = ""
    heard_phone: str = ""
    requested_check_in: str = ""
    requested_check_out: str = ""
    requested_room: str = ""

    # PERISHABLE. Availability was true when it was checked and may not be true
    # now — another caller can take the last room between two turns of this
    # conversation. Kept so the agent knows it already asked and what it said,
    # NOT so it can answer from memory. The note says so in as many words.
    availability: dict = field(default_factory=dict)

    # One-way actions that actually completed, in the order they happened.
    promises: list = field(default_factory=list)

    # Raw tool results, kept only so services/voice_agent/grounding.py can ask
    # whether a number the agent said came from anywhere. Never sent to the
    # model — the note above is what the model sees. Bounded so a long call
    # cannot grow it without limit.
    evidence: list = field(default_factory=list)

    # Tool arguments that are really the caller talking. The model is passing
    # back what it heard, so this is where a stranger's details enter the
    # system — the only place, until a booking exists to hold them.
    _FROM_CALLER = {
        "guest_name": "heard_name",
        "guest_email": "heard_email",
        "guest_phone": "heard_phone",
        "check_in_date": "requested_check_in",
        "check_out_date": "requested_check_out",
        "room_type": "requested_room",
    }

    def heard(self, args: dict) -> None:
        """Keep what the caller gave us, before any tool has verified it.

        Called with the arguments of every tool, because a name reaching
        lookup_booking and a name reaching create_booking_request are the same
        caller saying the same thing. Never overwrites with an empty value: the
        model routinely omits a field it already gave.
        """
        if not isinstance(args, dict):
            return
        for key, attr in self._FROM_CALLER.items():
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                setattr(self, attr, value.strip())

    def hear_caller(self, said: str, agent_asked: str = "") -> None:
        """Take what we can off the caller's own words, before any tool runs.

        heard() reads tool ARGUMENTS, which only carry a detail when the model
        chooses to pass it — measured on new-caller-long, the email was spelled
        out on turn 4 and never reached a tool, so it was gone by turn 17. The
        caller's sentence is evidence the model did not author, which is the
        same reason the booking gate reads the transcript.

        `agent_asked` is the agent's preceding question, and it is what tells a
        spelled NAME from a spelled anything-else. Callers spell emails and
        references far more often than names, and the letters look identical:
        "j o h n s m i t h at gmail dot com" assembled to a name called
        "Johnsmith", which then blocked every correctly-spelled name for the
        rest of the call. The cue is frequently not in the caller's sentence at
        all — "It is o then Epistroph, then c o n n o r" is a real turn, and it
        is only a name because the agent had just asked for one.
        """
        if not said:
            return
        try:
            from services.voice_agent.text_utils import (
                extract_spelled_words, extract_spoken_email)
            spoken = extract_spoken_email(said)
            if spoken:
                self.heard_email = spoken
        except Exception as exc:   # pragma: no cover - never break a turn
            logger.debug("hear_caller: email extraction failed — %s", exc)

        try:
            # An address already claimed this sentence. The same letters cannot
            # also be a name, and guessing wrong here is not a missed detail —
            # it poisons the booking gate for the whole call.
            if spoken:
                return
            if not _SPELLING_A_NAME.search(f"{agent_asked} {said}"):
                return
            spelled = extract_spelled_words(said)
            if spelled:
                self.spelled_name = " ".join(spelled)
        except Exception as exc:   # pragma: no cover - never break a turn
            logger.debug("hear_caller: spelling extraction failed — %s", exc)

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
            ("guest_email", "guest_email"),
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
            if self.guest_email:
                stay.append(f"email on the booking {self.guest_email}")
            lines.append(f"- Their booking: {', '.join(stay)}.")

        if self.promises:
            lines.append(f"- Already done on this call: {'; '.join(self.promises)}.")

        # What the caller told us and nothing has verified. Kept apart from the
        # settled facts on purpose: the agent must be able to tell the
        # difference between "the database says this" and "I think I heard
        # this", because only one of them is safe to act on.
        heard = []
        if self.spelled_name:
            heard.append(
                f"name the caller SPELLED OUT, letter by letter: {self.spelled_name} "
                f"— use this exact spelling. They spelled it because they expect "
                f"the sound to be misheard, and it usually is."
            )
        if self.heard_name and self.heard_name.lower() != self.spelled_name.lower():
            label = "name as heard (unreliable — see the spelling above)" \
                if self.spelled_name else "name as heard"
            heard.append(f"{label}: {self.heard_name}")
        if self.heard_email:
            heard.append(f"email as heard: {self.heard_email}")
        if self.heard_phone:
            heard.append(f"phone as heard: {self.heard_phone}")
        if self.requested_check_in:
            stay = self.requested_check_in
            if self.requested_check_out:
                stay += f" to {self.requested_check_out}"
            heard.append(f"dates asked for: {stay}")
        if self.requested_room:
            heard.append(f"room asked for: {self.requested_room}")

        # Perishable, and labelled as such. A room that was free when it was
        # checked can be taken by another caller before this sentence ends.
        perishable = [f"{what} — {verdict}" for what, verdict in self.availability.items()]

        if not (lines or heard or perishable):
            return ""

        note = []
        if lines:
            note.append(
                "CALL STATE — established earlier in this call and kept for you by "
                "the system, because the tool results that produced them are no "
                "longer in your context. Treat these as things you already know: "
                "answer from them directly rather than saying you cannot see "
                "them.\n" + "\n".join(lines)
            )
        if heard:
            note.append(
                "FROM THE CALLER, NOT YET VERIFIED — this is what they told you, "
                "kept so you do not have to ask twice. It has not been checked "
                "against anything. Use it to avoid re-asking, and read it back "
                "for confirmation before you book, email or charge on the "
                "strength of it.\n" + "\n".join(f"- {h}" for h in heard)
            )
        if perishable:
            note.append(
                "AVAILABILITY YOU ALREADY QUOTED — true when it was checked, not "
                "necessarily true now: another caller can take the last room "
                "between two of your turns. Say what you said before so you do "
                "not contradict yourself, and CHECK AGAIN before you promise a "
                "room or take a booking on it.\n"
                + "\n".join(f"- {p}" for p in perishable)
            )
        return "\n\n".join(note)
