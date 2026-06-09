"""
ASR Noise Simulator — Phase 2 Voice Emulation Layer.

Simulates real-world Deepgram speech-to-text transcription errors on clean
text inputs before they reach the multi-agent evaluation harness.

This bridges Phase 1 (deterministic correctness) → Phase 2 (voice-realistic
behavior) without requiring Twilio calls.

Each noise profile mimics a specific ASR failure mode:
  - "clean"  : No corruption. Phase 1 baseline.
  - "light"  : Minor word-error rate (~10%). Light punctuation loss.
  - "medium" : 25% WER + punctuation loss + date corruption.
  - "heavy"  : 40% WER + partial sentences + name/date corruption.

Usage:
    sim = ASRNoiseSimulator(seed=42)  # deterministic for reproducibility
    degraded = sim.apply_noise_profile("I'd like a queen room for May 30th", "medium")
    # -> "id like a queen room for may 13"

Part of the 3-Phase Evaluation Pipeline:
    Phase 1: clean input -> agent -> score
    Phase 2: degraded input -> agent -> score
    Delta   : phase_1_score - phase_2_score = Voice Realism Resistance metric
"""

import re
import random
from typing import Optional


# ---------------------------------------------------------------------------
# Room Type Corruption Map
# Simulates common Deepgram misrecognition patterns for hospitality terms
# ---------------------------------------------------------------------------
ROOM_CORRUPTION = {
    "queen": ["green", "keen", "cream", "clean"],
    "twin": ["tin", "ten", "thin", "win"],
    "family": ["famly", "fambly", "emily", "family room"],
    "accessible": ["assessable", "accessible room", "access", "special"],
    "double": ["duple", "trouble", "couple"],
    "king": ["keen", "thing", "sing"],
}

# ---------------------------------------------------------------------------
# Date Corruption Map
# Simulates ordinal/spoken-number misrecognition
# ---------------------------------------------------------------------------
DATE_CORRUPTION = {
    "30th": ["13th", "third", "thirtieth", "thirty"],
    "31st": ["21st", "first", "thirty-first"],
    "29th": ["19th", "twenty-ninth", "29"],
    "28th": ["18th", "twenty eighth", "28"],
    "15th": ["50th", "15", "fifteenth", "fiftieth"],
    "may": ["may", "make", "mail"],
    "june": ["june", "soon", "moon"],
    "july": ["july", "julie", "jewel"],
    "august": ["august", "aghast", "all gust"],
    "january": ["january", "januay", "janury"],
    "february": ["february", "feburary", "febry"],
    "friday": ["friday", "fried day", "fly day"],
    "saturday": ["saturday", "satday", "sad day"],
    "sunday": ["sunday", "sun day", "son day"],
    "monday": ["monday", "mon day"],
}

# ---------------------------------------------------------------------------
# Name Corruption — common STT errors on Australian names
# ---------------------------------------------------------------------------
NAME_CORRUPTION_RULES = [
    # Drop last character (partial transcription)
    (r'\b([A-Z][a-z]{4,})\b', lambda m: m.group(0)[:-1]),
    # Swap common homophones
    (r'\bJohn\b', 'Jon'),
    (r'\bSarah\b', 'Sara'),
    (r'\bSmith\b', 'Smit'),
    (r'\bBrown\b', 'Brawn'),
    (r'\bJames\b', 'Jaims'),
    (r'\bEmily\b', 'Emly'),
]

# ---------------------------------------------------------------------------
# Punctuation that STT commonly drops
# ---------------------------------------------------------------------------
PUNCTUATION_TO_DROP = [',', '.', '?', '!', ';', ':']

# ---------------------------------------------------------------------------
# Filler words STT inserts randomly
# ---------------------------------------------------------------------------
STT_INSERTIONS = ['uh', 'um', 'like', 'kind of', 'sort of', 'you know', '']


class ASRNoiseSimulator:
    """
    Simulates ASR transcription noise on clean text inputs.

    All corruption is deterministic when `seed` is provided — critical for
    reproducible evaluation runs where Phase 1 and Phase 2 can be compared
    fairly across identical scenario inputs.
    """

    PROFILES = {
        "clean": {"wer": 0.0, "punctuation_loss": False, "date_corruption": False, "name_corruption": False, "partial": False},
        "light": {"wer": 0.10, "punctuation_loss": True, "date_corruption": False, "name_corruption": False, "partial": False},
        "medium": {"wer": 0.25, "punctuation_loss": True, "date_corruption": True, "name_corruption": False, "partial": False},
        "heavy": {"wer": 0.40, "punctuation_loss": True, "date_corruption": True, "name_corruption": True, "partial": True},
    }

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def apply_noise_profile(self, text: str, profile: str = "medium") -> str:
        """
        Apply a named noise profile to clean text, returning degraded input.

        Args:
            text:    Clean user utterance (as a human would type it).
            profile: One of "clean", "light", "medium", "heavy".

        Returns:
            Degraded utterance simulating ASR transcription output.
        """
        if profile not in self.PROFILES:
            raise ValueError(f"Unknown profile '{profile}'. Valid: {list(self.PROFILES.keys())}")

        cfg = self.PROFILES[profile]

        if cfg["wer"] == 0.0 and not any(cfg.values()):
            return text  # clean pass-through

        result = text

        # Apply transformations in order of natural STT degradation pipeline
        if cfg["date_corruption"]:
            result = self.corrupt_dates(result)

        if cfg["name_corruption"]:
            result = self.corrupt_names(result)

        if cfg["wer"] > 0.0:
            result = self.corrupt_room_type(result)
            result = self.apply_word_error_rate(result, cfg["wer"])

        if cfg["punctuation_loss"]:
            result = self.drop_punctuation(result)

        if cfg["partial"]:
            result = self.partial_transcription(result, completion_pct=0.72)

        return result.strip()

    # -------------------------------------------------------------------------
    # Individual Corruption Methods
    # -------------------------------------------------------------------------

    def corrupt_room_type(self, text: str) -> str:
        """
        Misrecognize hospitality room-type terms.

        Example: "queen room" -> "green room"
        """
        result = text.lower()
        for correct, variants in ROOM_CORRUPTION.items():
            if correct in result and self._rng.random() < 0.55:
                replacement = self._rng.choice(variants)
                result = result.replace(correct, replacement, 1)
        return result

    def corrupt_dates(self, text: str) -> str:
        """
        Misrecognize date ordinals and month names.

        Example: "May 30th" -> "may 13th" or "may thirty"
        """
        result = text.lower()
        for correct, variants in DATE_CORRUPTION.items():
            pattern = r'\b' + re.escape(correct) + r'\b'
            if re.search(pattern, result) and self._rng.random() < 0.45:
                replacement = self._rng.choice(variants)
                result = re.sub(pattern, replacement, result, count=1)
        return result

    def corrupt_names(self, text: str) -> str:
        """
        Apply STT name misrecognition patterns.

        Example: "Sarah Smith" -> "Sara Smit"
        """
        result = text
        for pattern, replacement in NAME_CORRUPTION_RULES:
            if self._rng.random() < 0.4:
                if callable(replacement):
                    result = re.sub(pattern, replacement, result, count=1)
                else:
                    result = re.sub(pattern, replacement, result, count=1)
        return result

    def drop_punctuation(self, text: str) -> str:
        """
        Remove punctuation marks — raw STT output style.

        Example: "I'd like a room, please." -> "id like a room please"
        """
        result = text
        for char in PUNCTUATION_TO_DROP:
            result = result.replace(char, '')
        # Also lowercase (STT typically outputs lowercase without capitalization)
        result = result.lower()
        return result

    def apply_word_error_rate(self, text: str, wer: float) -> str:
        """
        Apply approximate word error rate by randomly dropping or substituting words.

        STT errors skew toward dropping words at word boundaries, not random
        mid-word corruption. Simulates the Deepgram Nova-2 failure distribution.
        """
        words = text.split()
        if not words:
            return text

        result_words = []
        for word in words:
            roll = self._rng.random()
            if roll < wer * 0.6:
                # Drop word entirely
                continue
            elif roll < wer:
                # Insert random filler before this word
                filler = self._rng.choice(STT_INSERTIONS)
                if filler:
                    result_words.append(filler)
                result_words.append(word)
            else:
                result_words.append(word)

        return ' '.join(result_words)

    def partial_transcription(self, text: str, completion_pct: float = 0.70) -> str:
        """
        Simulate incomplete utterance delivery — STT cuts off before sentence ends.

        Example: "I want to book a queen room for the weekend please"
                 -> "I want to book a queen room for the"  (at 70%)
        """
        words = text.split()
        if not words:
            return text
        cutoff = max(1, int(len(words) * completion_pct))
        return ' '.join(words[:cutoff])

    def generate_scenario_variants(self, clean_input: str) -> dict:
        """
        Generate all 4 noise-profile variants for a single input.

        Returns a dict with profile names as keys and degraded text as values.
        Useful for comparative evaluation output.
        """
        return {
            profile: self.apply_noise_profile(clean_input, profile)
            for profile in self.PROFILES
        }


# ---------------------------------------------------------------------------
# Standalone test (run directly)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sim = ASRNoiseSimulator(seed=42)

    test_inputs = [
        "I'd like to book a queen room from May 30th to June 1st.",
        "My name is Sarah Smith and my email is sarah@gmail.com",
        "Do you have any twin rooms available this Saturday?",
        "Can I get a family room for the upcoming weekend please?",
    ]

    for text in test_inputs:
        print(f"\n{'='*60}")
        print(f"CLEAN : {text}")
        variants = sim.generate_scenario_variants(text)
        for profile, degraded in variants.items():
            delta = "→ same" if degraded == text else f"→ {degraded}"
            print(f"{profile.upper():8s}: {delta}")
