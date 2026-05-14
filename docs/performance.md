# Performance tuning

End-to-end latency for a voice query (wake → response → audio playback) is dominated by the LLM hop. With unoptimized defaults, expect 6-10 seconds. With the tweaks below, ~3-5 seconds.

## Latency stack (typical)

| Stage | Time | Notes |
|---|---|---|
| Wake-word detection | ~30 ms | Hardware-bound (micro_wake_word on ESP32) |
| Mic stream to HA | ~50-100 ms | Wifi-bound |
| STT (faster-whisper) | ~500-1500 ms | Model size matters |
| **LLM (Claude Opus 4.7)** | **~3-8 s** | **Biggest target** |
| TTS (Piper) | ~500-1000 ms | Streaming helps |
| Audio fetch + playback | ~200-500 ms | Direct LAN path required |

## Tweak 1: trim the system prompt (foundation for cache)

The stock extended_openai_conversation prompt rebuilds an entity-state CSV inline every call. That CSV changes any time an entity's state changes, which kills prompt-cache hit rates AND adds 2-5k tokens of dynamic content per call.

Replace the entities block with instructions for the LLM to call `get_attributes` when it needs state. Sample prompt: see [`patches/voice_prompt.txt`](../patches/voice_prompt.txt).

Effect: rendered prompt becomes mostly static (~2k chars vs ~7-15k with full CSV expansion). Sets up cache hits in the next tweak.

## Tweak 2: enable Bedrock prompt caching via LiteLLM

LiteLLM can auto-inject `cache_control` blocks on system messages. For Bedrock Anthropic models this maps to `cachePoint` blocks with TTL options of 5min (default, 1.25x write cost) or 1h (2x write cost, but reads stay cheap and survive longer between voice queries).

Add to `/etc/litellm/config.yaml` `litellm_settings:`:

```yaml
litellm_settings:
  drop_params: true
  set_verbose: false
  cache_control_injection_points:
    - location: message
      role: system
      control:
        type: ephemeral
        ttl: 1h
```

Restart with `docker restart litellm`. Verify cache hits by timing two consecutive identical-prompt calls — second should be ~40% faster.

Measured improvement: 4.6s → 2.7s (-42%) for the LLM hop on a representative voice query.

## Tweak 3 (optional): switch Opus → Haiku for voice

Opus 4.7 is overkill for most voice queries ("turn on the kitchen lights", "what time is it"). Haiku 4.5 is 5-10x faster and ~12x cheaper, with adequate intelligence for voice commands.

Two paths to do this without losing Opus access:
- A. Change the pipeline's `conversation_engine` to a Haiku-backed entry in LiteLLM (`claude-haiku` is already configured in the LiteLLM `model_list`).
- B. Use the secondary wake-word slot for Opus and primary for Haiku — say "okay nabu" for hard questions, your daily wake word for fast/simple ones.

JP chose to keep Opus across the board for now (2026-05-14).

## Tweak 4 (optional): streaming TTS

By default the voice satellite waits for Piper to finish synthesizing the full WAV, then fetches + plays. Streaming TTS lets audio start playing while Claude is still emitting tokens.

Requires both:
- ESPHome firmware that uses `voice_assistant.on_tts_stream_start` / `on_tts_stream_end` handlers
- HA pipeline + TTS engine that emits chunked output

The M5Stack ATOM Echo hardware can handle streaming playback. Currently not enabled in our setup — the `media_player.speaker` flow we use does support chunked HTTP fetch and will benefit if HA's tts_proxy emits chunks as Piper synthesizes.

## Tweak 5 (optional): tighter VAD

`select.<device>_finished_speaking_detection` has options `default`, `relaxed`, `aggressive`. Switching to `aggressive` cuts ~500-1000 ms off the post-speech wait.

Tradeoff: it can clip the end of slow speakers. Defer this on devices used by kids or older users.

## Tweak 6: prompt caching tradeoffs to be aware of

- The cache requires identical PREFIX. Any change to the prompt (including time-of-day tokens like `{{ now() }}`) WILL invalidate the cache for the rest of that conversation turn. Keep dynamic content at the END of the message list, not in the system prompt, when possible.
- The voice-assistant subentry's prompt template includes `{{ now() }}` and `{{ area_id(...) }}`. These render fresh each turn but are SHORT and at the top, so they don't blow the cache for longer prefixes.
- Bedrock's `cachePoint` is per-region per-account. The `us.anthropic.claude-opus-4-7` model in us-east-1 keeps its own cache.
