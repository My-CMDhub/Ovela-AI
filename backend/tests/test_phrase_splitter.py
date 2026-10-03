"""
tests/test_phrase_splitter.py
=============================
The splitter cuts the model's stream into phrases, and prepare_for_tts
normalises each phrase ON ITS OWN. A cut inside a token is therefore spoken
wrong, and the old splitter cut at the first . , : anywhere:

    'The room is $129.50 per night.'  -> 'The room is 129 dollars.' + '50 per night.'
    'I have ada@example.com on file.' -> 'I have ada@example.' + 'com on file.'
    'Check-in is at 2:30 p.m. tomorrow.' -> '...at 2:' + '30 p.' + 'm.' + 'tomorrow.'

The booking read-back prompt has the model say "$[price] per night" and the
caller's email back to them, so this hit the turn that matters most.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.voice_agent.cascaded_orchestrator import (
    CascadedPipelineOrchestrator,
    split_buffer_into_phrases,
)
from services.voice_agent.text_utils import prepare_for_tts


def _stream(tokens):
    """Feed tokens the way the pipeline's sender loop does: one split per
    token with is_final=False, then a final split once the stream has ended."""
    phrases, buf = [], ""
    for token in tokens:
        buf += token
        out, buf = split_buffer_into_phrases(buf, is_final=False)
        phrases += out
    out, buf = split_buffer_into_phrases(buf, is_final=True)
    assert buf == ""
    return phrases + out


def _spoken(phrases):
    """What Cartesia is sent: each phrase normalised separately, stripped."""
    return " ".join(p for p in (prepare_for_tts(ph)[0].strip() for ph in phrases) if p)


@pytest.mark.parametrize("sentence", [
    "The room is $129.50 per night.",
    "That comes to 3.5 nights at $1,250.",
    "I have ada@example.com on file.",
    "Is that jane.smith@gmail.com, right?",
    "Check-in is at 2:30 p.m. tomorrow.",
])
def test_a_whole_sentence_is_not_cut_inside_a_token(sentence):
    phrases, rest = split_buffer_into_phrases(sentence, is_final=True)
    assert rest == ""
    assert _spoken(phrases) == prepare_for_tts(sentence)[0].strip()


def test_the_email_is_spoken_as_an_address():
    phrases, _ = split_buffer_into_phrases("I have ada@example.com on file.", is_final=True)
    assert "ada at example dot com" in _spoken(phrases)


def test_a_price_streamed_token_by_token_is_spoken_like_the_whole_sentence():
    tokens = ["The room is ", "$129", ".", "50 per", " night."]
    phrases = _stream(tokens)
    assert _spoken(phrases) == prepare_for_tts("".join(tokens))[0].strip()
    assert not any(p.strip().startswith("50") for p in phrases)


@pytest.mark.parametrize("tokens", [
    ["I have ", "ada", "@example", ".", "com", " on file."],
    ["Check-in is at ", "2", ":", "30 p", ".", "m", ".", " tomorrow."],
    ["Your total is ", "$1", ",", "250", ".", "00, ", "is that okay?"],
])
def test_streamed_tokens_are_spoken_like_the_whole_sentence(tokens):
    assert _spoken(_stream(tokens)) == prepare_for_tts("".join(tokens))[0].strip()


def test_trailing_punctuation_waits_for_the_next_token_until_the_stream_ends():
    phrases, rest = split_buffer_into_phrases("The room is $129.", is_final=False)
    assert phrases == []
    assert rest == "The room is $129."

    phrases, rest = split_buffer_into_phrases("The room is $129.", is_final=True)
    assert phrases == ["The room is $129."]
    assert rest == ""


@pytest.mark.parametrize("text,first", [
    ("Your host is Mr. Patel, and he says hi.", "Your host is Mr. Patel,"),
    ("Ask for Dr. Lee. She is in today.", "Ask for Dr. Lee."),
    ("We open at 7 a.m. and close late.", "We open at 7 a.m. and close late."),
    ("Bring towels, e.g. beach ones.", "Bring towels,"),
    ("It is on Main ST. by the park.", "It is on Main ST. by the park."),
])
def test_no_split_after_a_common_abbreviation(text, first):
    phrases, _ = split_buffer_into_phrases(text, is_final=True)
    assert phrases[0] == first


def test_ordinary_sentences_still_split_at_full_stops_and_commas():
    phrases, rest = split_buffer_into_phrases("Yes, we have rooms. Would you like one", is_final=False)
    assert phrases == ["Yes,", " we have rooms."]
    assert rest == " Would you like one"

    phrases, rest = split_buffer_into_phrases("Great! Is that all? Thanks; bye: now", is_final=True)
    assert phrases == ["Great!", " Is that all?", " Thanks;", " bye:", "now"]
    assert rest == ""


def test_the_length_split_never_cuts_a_word_that_is_still_arriving():
    # Six words, but the sixth may still be growing into an address.
    phrases, rest = split_buffer_into_phrases("I have it down as ada@exam", is_final=False)
    assert phrases == []
    assert rest == "I have it down as ada@exam"

    phrases, rest = split_buffer_into_phrases("so that is two nights at $129.50 each", is_final=False)
    assert phrases == ["so that is two nights at"]
    assert rest == " $129.50 each"

    assert _spoken(_stream(["I have it down as ada", "@exam", "ple.com, ", "right?"])) == \
        prepare_for_tts("I have it down as ada@example.com, right?")[0].strip()


def _delta(content=None, tool_calls=None):
    ev = MagicMock()
    ev.choices = [MagicMock()]
    ev.choices[0].delta.content = content
    ev.choices[0].delta.tool_calls = tool_calls
    return ev


@pytest.mark.asyncio
async def test_speech_before_a_tool_call_is_released_before_the_tool_runs():
    """
    The splitter holds a trailing "." for the next token, and before a tool
    call the next token comes from the NEXT model round — after the lookup,
    and with no leading space. The model's own "Let me check those dates."
    must be closed off when the tool call starts, not merged into the answer.
    """
    agent = CascadedPipelineOrchestrator(twilio_ws=AsyncMock(), stream_sid="MZtest")
    agent.is_running = True

    tc = MagicMock()
    tc.index, tc.id = 0, "call_0"
    tc.function.name = "check_availability"
    tc.function.arguments = "{}"

    async def round_one(*_a, **_kw):
        yield _delta(content="Let me check those dates.")
        yield _delta(tool_calls=[tc])

    async def round_two(*_a, **_kw):
        yield _delta(content="Great news, the Queen is free.")

    agent._context_ready = True
    agent.tenant_config = {"voice_settings": {"llm_model": "gpt-4.1-nano"}}
    agent.dispatcher = MagicMock(caller_reservation=AsyncMock(return_value=[]))
    seen_before_tool = []

    async def execute(*_a, **_kw):
        seen_before_tool.extend(_stream_so_far)
        return {"ok": True}

    agent.dispatcher.execute = AsyncMock(side_effect=execute)
    agent._openai = MagicMock()
    agent._openai.chat.completions.create = AsyncMock(side_effect=[round_one(), round_two()])

    _stream_so_far, buf = [], ""
    async for token in agent._default_llm_callback(
            [{"role": "user", "content": "is the queen free on friday?"}]):
        buf += token
        out, buf = split_buffer_into_phrases(buf, is_final=False)
        _stream_so_far += out
    out, _ = split_buffer_into_phrases(buf, is_final=True)
    phrases = [p.strip() for p in _stream_so_far + out]

    assert seen_before_tool == ["Let me check those dates."]
    assert phrases == ["Let me check those dates.", "Great news,", "the Queen is free."]
