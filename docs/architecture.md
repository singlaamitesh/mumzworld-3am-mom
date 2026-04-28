# Architecture

## Component diagram

```
┌─────────────────────────────────────────────┐
│ app.py (Streamlit)                           │
│  - text chat (default, reliable)             │
│  - voice toggle: streamlit-webrtc mic        │
│  - escalation banner, product cards, RTL     │
└──────────────┬──────────────┬───────────────┘
               │ user_text    │ audio chunks
               ▼              ▼
┌─────────────────────────────────────────────┐
│ src/agent.py — Agent                         │
│  - turn(text)   → Gemini 2.5 Flash (free)   │
│  - stream(audio)→ Gemini 3.1 Flash Live      │
│  Both share system prompt + tool defs        │
└──────────────────────┬──────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
   ┌──────────────────┬──────────────────┬─────────────────┐
   │ escalation_check │ knowledge_search │ product_search  │
   │ NICE NG143 regex │ LanceDB+Nemotron │ LanceDB+Nemotron│
   └──────────────────┴──────────────────┴─────────────────┘

┌─────────────────────────────────────────────┐
│ evals/run_evals.py                           │
│  agent.turn() per case → judge (2.5 Pro)    │
│  → evals/results.json                        │
│  (voice path is NOT exercised by evals)     │
└─────────────────────────────────────────────┘
```

## Data flow per turn

**Text mode (eval-graded path):**
1. User types text → reaches `Agent.turn(user_text)`.
2. Agent sends to Gemini 2.5 Flash via `generate_content` with system prompt + 3 function declarations.
3. Model emits `function_call`. Agent executes locally:
   - `escalation_check` returns NICE category triggers (deterministic regex).
   - `knowledge_search` embeds query → LanceDB cosine → top-k chunks (filter at confidence ≥ 0.5).
   - `product_search` embeds query → LanceDB cosine → top-k products (optional age filter).
4. Agent sends `function_response` back; loop until model emits final text.
5. Logged as `AgentResponse` for evals and UI.

**Voice mode (stretch demo):**
1. Browser mic → streamlit-webrtc → PCM16 chunks → `Agent.stream(audio_chunks)`.
2. Live API session opens with the same system prompt + tools as text mode.
3. Server streams back `transcript_user`, `transcript_agent`, `audio` (PCM16 24kHz), and `tool_call` events.
4. Tool calls executed identically to text mode; responses sent back via `send_tool_response`.
5. UI renders transcripts in real-time and plays audio chunks back.

## Why these choices

See [docs/tradeoffs.md](tradeoffs.md).
