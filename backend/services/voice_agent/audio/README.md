# System Audio Clips (Twilio μ-law, 8kHz)

This directory stores pre-generated low-latency system prompts used by `VoiceAgentHandler`.

## Format
- File format: raw μ-law bytes (`.mulaw.raw`)
- Encoding: `pcm_mulaw`
- Sample rate: `8000`
- Container: raw/no header

## Directory layout
- `audio/<voice_id>/<clip_key>.mulaw.raw`
- `audio/default/<clip_key>.mulaw.raw` (fallback)

## Clip keys currently used
- `smart_greeting`
- `silence_soft`
- `silence_hard`
- `abuse_warning`
- `filler_short`
- `filler_long`
- `transfer`
- `transfer_failed`
- `farewell`
- `duration_soft`

## Example
`audio/a167e0f3-df7e-4d52-a9c3-f949145efdab/silence_soft.mulaw.raw`

Use the script at `backend/services/voice_agent/generate_system_audio_clips.py` to generate these clips from Cartesia.
