# Architecture

## Component diagram

```
┌─────────────────────────────────────────────────────┐
│  voice/static/index.html  (custom HTML/CSS/JS)      │   ← headline UX
│  Mumzworld pink-coral · Fraunces · animated orb     │
│  AudioWorklet capture · gapless 24kHz playback      │
│  RTL transcripts · escalation banner · product cards│
└───────────────────────┬─────────────────────────────┘
                        │ WebSocket (binary + JSON)
                        ▼
┌─────────────────────────────────────────────────────┐
│  voice/server.py  (FastAPI)                         │
│  - bridges browser ↔ Gemini Live both ways          │
│  - session lifecycle: 60s idle, 10min hard cap      │
│  - VAD-aware silence detection on PCM frames        │
│  - executes tool calls locally, forwards results    │
└───────────────┬─────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────┐
│  Gemini 3.1 Flash Live preview                      │
│  bidirectional audio + per-turn function calling    │
└────┬───────────────────┬────────────────────┬───────┘
     │                   │                    │
     ▼                   ▼                    ▼
escalation_check   knowledge_search       product_search
NICE NG143 regex   LanceDB + Nemotron     LanceDB + Nemotron
(EN+AR, no LLM)    Embed via OpenRouter   (with age filter)


┌─────────────────────────────────────────────────────┐
│  app.py  (Streamlit, secondary)                     │
│  text-only chat; calls Agent.turn() for each turn   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  src/agent.py — Agent.turn(text)                    │
│  OpenAI SDK pointed at OpenRouter (free tier)        │
│  GPT-OSS-120B, OpenAI tool-calling format           │
│  same system prompt + same three tools as voice     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  evals/run_evals.py                                 │
│  Agent.turn() per case → judge model on OpenRouter  │
│  judge = GLM-4.5-Air (different family from agent)  │
│  → evals/results.json                               │
└─────────────────────────────────────────────────────┘
```

## Data flow per turn

### Voice mode (headline UX)

1. Browser captures mic at the native rate (typically 48kHz mono) via `AudioWorkletNode`. JS resamples to 16kHz PCM16, sends as binary WebSocket frames every ~100ms.
2. `voice/server.py` forwards each frame to the open Gemini Live session via `send_realtime_input`. RMS-amplitude VAD on the server side determines whether the frame counts as "speech" for the idle watchdog.
3. Gemini Live emits a per-turn async generator. The server pumps:
   - `input_transcription` → JSON `{"type":"transcript_user","text":...}` to browser
   - `output_transcription` → JSON `{"type":"transcript_agent","text":...}`
   - `model_turn` audio (`inline_data`, PCM16 24kHz) → binary WebSocket frame
   - `tool_call` → server runs the tool locally, sends `{"type":"tool_call",...}` then `{"type":"tool_done",...}` to browser, replies to Gemini with `send_tool_response`
   - `turn_complete` → JSON `{"type":"turn_complete"}`
4. The browser plays audio gaplessly via `AudioBufferSourceNode` scheduled against a rolling `playbackHead`, and merges incremental transcripts into chat bubbles (handles cumulative vs incremental SDK variants).
5. After `turn_complete`, the server re-enters `session.receive()` for the next turn — the session stays open across multi-turn conversations.

### Text mode (eval-graded path)

1. User types text → reaches `Agent.turn(user_text)` via Streamlit chat or the eval runner.
2. Agent sends a chat-completions request to OpenRouter with the same system prompt + three tools declared in OpenAI function-calling format.
3. Model emits `tool_calls`. Agent executes locally:
   - `escalation_check` returns NICE category triggers (deterministic regex; no LLM).
   - `knowledge_search` embeds query → LanceDB cosine → top-k chunks (filter at `KB_MIN_CONFIDENCE = 0.3`).
   - `product_search` embeds query → LanceDB cosine → top-k products (filter at `PRODUCT_MIN_CONFIDENCE = 0.45`, optional age-range overlap).
4. Agent appends tool messages, loops until the model emits final text.
5. Returns `AgentResponse` (Pydantic) — used by the Streamlit UI and logged by the eval runner.

## Why these choices

See [docs/tradeoffs.md](tradeoffs.md).
