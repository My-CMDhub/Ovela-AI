"""
Turn-taking, measured from the audio: when the caller really stopped, and what
happened when both sides spoke at once.

`call_trace.py` starts its clock when Deepgram DECLARES the turn over. A caller
starts theirs at their last word. On 20 Sep the difference (Deepgram's wait plus
phone transport) was 0.27-0.84 s of a 0.9-1.7 s gap; on real calls it is larger. Only the recording knows the last word, so this reads
the dual-channel recording: one speaker per channel, the same webrtcvad the
pipeline uses (20 ms frames, aggressiveness 3), no transcript, no logs.

Per call it reports:
  gaps       caller's last voiced frame -> agent's first voiced frame, for every
             floor handover caller -> agent. Negative = the agent started over them.
  early      handovers where the caller spoke again within EARLY_S of the agent
             starting: the agent answered someone who had not finished. A
             candidate list to listen to, not a verdict — a caller who says
             "yes" over the agent's first word lands here too.
  overlaps   every stretch where both channels were voiced while the agent held
             the floor: who went quiet first, and how long the agent took to yield.

What it cannot say: whether the agent resumed or restarted after a barge-in
(that is in the words; today the code always discards the rest and starts a new
turn), and anything about an edited recording's cut points — a trimmed pause
reads as a short gap. Measure originals. A noisy caller track (street, car)
reads as speech throughout; the run warns and its numbers are not usable.

Usage (from backend/):
    python -m scripts.turn_gaps call.wav                  # agent = channel that speaks first
    python -m scripts.turn_gaps call.mp3 --agent 1 --json
"""
import argparse
import json
import statistics
import subprocess
import sys

import webrtcvad

RATE, FRAME = 8000, 160          # 20 ms at 8 kHz, as on the Twilio leg
HANGOVER_S = 0.30                # a pause shorter than this is inside a spurt
MIN_SPURT_S = 0.12               # shorter voiced runs are clicks and line noise
EARLY_S = 1.0                    # caller back within this of agent onset = candidate early answer
# The fastest turn ever measured, EndOfTurn -> audio, was 476 ms (20 Sep). A
# shorter "gap" is not a reply to that spurt: it is the reply to an earlier one
# landing just after the caller said something short. Counted, not averaged.
REPLY_FLOOR_S = 0.45
# 18 Sep, real call from a noisy place: the caller track read "voiced" 57% of
# the call (clean calls: ~20%) and every number came out as nonsense, silently.
NOISY_CALLER = 0.45


def channels(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "2",
                          "-ar", str(RATE), "-"], capture_output=True, check=True).stdout
    left, right = bytearray(), bytearray()
    for i in range(0, len(raw) - 3, 4):
        left += raw[i:i + 2]
        right += raw[i + 2:i + 4]
    return bytes(left), bytes(right)


def spurts(pcm, vad=None):
    """[(start_s, end_s)] of voiced speech, pauses under HANGOVER_S bridged."""
    vad = vad or webrtcvad.Vad(3)
    step = FRAME * 2
    out = []
    for n in range(len(pcm) // step):
        if vad.is_speech(pcm[n * step:(n + 1) * step], RATE):
            t = n * 0.02
            if out and t - out[-1][1] <= HANGOVER_S:
                out[-1][1] = t + 0.02
            else:
                out.append([t, t + 0.02])
    return [(round(a, 2), round(b, 2)) for a, b in out if b - a >= MIN_SPURT_S]


def analyse(caller, agent):
    gaps, early, overlaps = [], [], []
    for i, (c_start, c_end) in enumerate(caller):
        if any(a[0] < c_end < a[1] for a in agent):
            continue                                   # agent held the floor: an overlap, below
        answer = next((a[0] for a in agent if a[0] >= c_end), None)
        resumed = caller[i + 1][0] if i + 1 < len(caller) else None
        if answer is None or (resumed is not None and resumed < answer):
            continue                                   # the caller carried on: a pause, not a handover
        gaps.append({"at_s": answer, "caller_stopped_s": c_end, "gap_s": round(answer - c_end, 2)})
        back = resumed if resumed is not None and resumed < answer + EARLY_S else None
        if back is not None:
            early.append({"agent_started_s": answer, "caller_back_s": back,
                          "why": "caller spoke again within %.1f s of the answer" % EARLY_S})
    for a_start, _ in agent:
        talking = next((c for c in caller if c[0] < a_start < c[1]), None)
        if talking and not any(a[0] < talking[0] < a[1] for a in agent):
            early.append({"agent_started_s": a_start, "caller_back_s": None,
                          "why": "started %.2f s before the caller finished" % (talking[1] - a_start)})
    for c_start, c_end in caller:
        holding = next((a for a in agent if a[0] < c_start < a[1]), None)
        if not holding:
            continue                                   # not an interruption of the agent
        yielded = holding[1] <= c_end
        overlaps.append({"caller_started_s": c_start,
                         "yielded": "agent" if yielded else "caller",
                         "agent_stopped_after_s": round(holding[1] - c_start, 2) if yielded else None})
    return gaps, early, overlaps


def summary(gaps, early, overlaps):
    g = sorted(x["gap_s"] for x in gaps if x["gap_s"] >= REPLY_FLOOR_S)
    p90 = g[min(len(g) - 1, int(0.9 * len(g)))] if g else None
    return {"handovers": len(g), "below_reply_floor": len(gaps) - len(g),
            "gap_median_s": statistics.median(g) if g else None,
            "gap_p90_s": p90, "early_candidates": len(early),
            "early_rate": round(len(early) / len(g), 2) if g else None,
            "overlap_count": len(overlaps),
            "agent_yielded": sum(o["yielded"] == "agent" for o in overlaps)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recording", help="dual-channel recording (wav or mp3)")
    ap.add_argument("--agent", type=int, choices=(0, 1),
                    help="agent's channel (default: whichever speaks first — the greeting)")
    ap.add_argument("--json", action="store_true", help="per-event detail as JSON")
    args = ap.parse_args()

    pcms = channels(args.recording)
    tracks = [spurts(pcm) for pcm in pcms]
    agent_ch = args.agent if args.agent is not None else min((0, 1), key=lambda i: tracks[i][0][0] if tracks[i] else 1e9)
    agent, caller = tracks[agent_ch], tracks[1 - agent_ch]
    gaps, early, overlaps = analyse(caller, agent)
    result = {"recording": args.recording, "agent_channel": agent_ch, **summary(gaps, early, overlaps)}
    seconds = len(pcms[0]) / (2 * RATE)
    voiced = sum(b - a for a, b in caller) / seconds if seconds else 0
    if voiced > NOISY_CALLER:
        result["warning"] = ("caller track voiced %.0f%% of the call: background noise, "
                             "not speech — these numbers are not usable" % (100 * voiced))
        print("WARNING: " + result["warning"], file=sys.stderr)
    if args.json:
        result.update(gaps=gaps, early=early, overlaps=overlaps)
    json.dump(result, sys.stdout, indent=2)
    print()


def _selfcheck():
    caller = [(2.0, 4.0), (6.5, 7.0), (9.0, 10.0), (12.0, 12.5)]
    agent = [(0.0, 1.5), (5.0, 8.0), (10.3, 11.0), (11.5, 14.0)]
    gaps, early, overlaps = analyse(caller, agent)
    assert [g["gap_s"] for g in gaps] == [1.0, 0.3], gaps    # 4.0->5.0, 10.0->10.3; 11.5 is mid-reply
    assert early == [], early                                # caller back at 6.5 is 1.5 s after onset
    assert [o["yielded"] for o in overlaps] == ["caller", "caller"], overlaps
    gaps, early, _ = analyse([(2.0, 4.0), (5.3, 6.0)], [(4.8, 9.0)])
    assert early[0]["caller_back_s"] == 5.3                  # agent at 4.8, caller back 0.5 s later
    # booking take, 30.8 s: the agent starts mid-sentence, stops, then answers properly
    gaps, early, _ = analyse([(27.2, 32.2)], [(30.8, 31.76), (33.1, 40.0)])
    assert [g["gap_s"] for g in gaps] == [0.9] and early[0]["why"].startswith("started 1.40"), (gaps, early)
    _, _, overlaps = analyse([(3.0, 5.0)], [(1.0, 3.4)])
    assert overlaps == [{"caller_started_s": 3.0, "yielded": "agent", "agent_stopped_after_s": 0.4}]
    print("selfcheck ok")


if __name__ == "__main__":
    _selfcheck() if sys.argv[1:] == ["--selfcheck"] else main()
