"""
services/voice_agent/interruption.py
======================================
Phase 12.1 — Telephony Mark-Tracking, Interruption Pruning,
State-Aware Routing, and Cognitive Pacing cues.
"""

from typing import List, Dict, Any
from services.voice_agent.vad import ConversationState, is_backchannel_word


class MarkTracker:
    """
    Tracks word delivery milestones echoed back by Twilio to measure how many
    words reached the caller's ear before barge-in.

    Marks carry the turn they belong to. They used to be named `mark_word_N`
    with nothing to say which turn that was, and Twilio keeps echoing marks
    for audio it had already queued when the barge-in landed. Those late
    echoes arrive during the NEXT turn, whose marks reuse the same names, so
    turn 1's `mark_word_18` confirmed turn 2's eighteenth word while the
    caller had heard three. `confirmed_index` is what barge-in prunes history
    against, so an index that runs ahead of the ear makes the agent believe
    the caller heard sentences that were never played — and it does not repeat
    them.
    """
    def __init__(self):
        self._registered_marks = set()
        self.confirmed_index = 0
        self.generation = 0

    def register_word(self, word_index: int) -> str:
        """
        Register a word index and generate its mark name for Twilio. The name
        carries this turn's generation so a late echo cannot be mistaken for
        one of ours.
        """
        mark_name = f"mark_t{self.generation}_w{word_index}"
        self._registered_marks.add(mark_name)
        return mark_name

    def confirm_mark(self, mark_name: str) -> None:
        """
        Confirm a mark echoed by Twilio if it belongs to this turn.

        Takes the furthest position confirmed, never simply the latest: marks
        usually arrive in order, and on the one occasion they do not, the ear
        does not travel backwards.
        """
        if mark_name not in self._registered_marks:
            return
        try:
            turn, _, word = mark_name.removeprefix("mark_t").partition("_w")
            if int(turn) != self.generation:
                return
            self.confirmed_index = max(self.confirmed_index, int(word))
        except (ValueError, IndexError):
            pass

    def reset(self) -> None:
        """
        Start a new turn: drop this turn's registrations and its index, and
        move the generation on so nothing echoed late can reach the new one.
        """
        self._registered_marks.clear()
        self.confirmed_index = 0
        self.generation += 1


def slice_to_confirmed_word(text: str, confirmed_word_index: int) -> str:
    """
    Slice text up to the exact word index confirmed by Twilio mark tracking.
    """
    if not text or confirmed_word_index <= 0:
        return ""
    words = text.split()
    return " ".join(words[:confirmed_word_index])


def prune_conversation_history(history: List[Dict[str, Any]], confirmed_word_index: int) -> List[Dict[str, Any]]:
    """
    Prune un-delivered words from the last assistant turn in the conversation history
    when an interruption occurs, rounding back to the last complete sentence boundary.
    """
    if not history:
        return []

    # Find the last assistant turn
    last_idx = -1
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") == "assistant":
            last_idx = i
            break

    if last_idx == -1:
        return history

    if confirmed_word_index <= 0:
        # User heard nothing of the last turn; drop it completely
        return history[:last_idx] + history[last_idx + 1:]

    content = history[last_idx].get("content", "")
    words = content.split()
    trimmed = " ".join(words[:confirmed_word_index])

    # If we cut mid-turn and the cut doesn't land exactly on a sentence boundary,
    # round back to the last complete sentence to avoid leaving a sentence fragment.
    if confirmed_word_index < len(words) and not trimmed.strip().endswith((".", "!", "?")):
        last_punct = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
        if last_punct != -1:
            trimmed = trimmed[:last_punct + 1].strip()

    new_history = list(history)
    new_history[last_idx] = dict(new_history[last_idx])
    new_history[last_idx]["content"] = trimmed
    return new_history


def route_transcript(transcript: str, state: ConversationState) -> str:
    """
    State-aware routing for incoming transcript snippets:
    - 'ignore': backchannel affirmation while AI is speaking, or empty/noise
    - 'interrupt': genuine correction or long speech while AI is speaking
    - 'forward': input when AI is awaiting input
    """
    if not transcript or not transcript.strip():
        return "ignore"

    if state == ConversationState.AGENT_SPEAKING:
        if is_backchannel_word(transcript):
            return "ignore"
        return "interrupt"

    # AWAITING_INPUT or other states: forward all non-empty transcripts
    return "forward"


def cognitive_delay(elapsed_s: float) -> float:
    """
    Calculate thinking cue delay in milliseconds (0 to 300ms) for fast tool responses
    so the assistant feels natural and considered rather than instantly robotic.
    """
    if elapsed_s < 0:
        elapsed_s = 0.0
    if elapsed_s >= 0.2:
        return 0.0
    # Fast tool call (< 200ms) returns 120ms cue
    return 120.0
