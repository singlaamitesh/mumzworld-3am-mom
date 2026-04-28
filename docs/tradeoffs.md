# Tradeoffs and decisions

## Two-model agent: text-mode 2.5 Flash, voice 3.1 Flash Live

The agent has two entry points sharing the same system prompt and tool definitions:
- `turn(text)` runs on free Gemini 2.5 Flash via `generate_content`. This is the rubric-graded path: the eval suite calls it 12 times across red flag, product, OOS, IDK, and Arabic cases.
- `stream(audio)` runs on Gemini 3.1 Flash Live preview (paid) for the voice demo. Voice does NOT touch the eval suite.

The split protects the rubric-graded path from preview SDK volatility. If Gemini 3.1 Flash Live signatures shift mid-build or the preview is unstable, `turn()` keeps working and the eval scores are unaffected. Voice ships as polish on top of a complete core, or gets explicitly documented as a known failure if it breaks.

Future work: if Live's Khaleeji audio is judged weak by a native reviewer, swap voice ASR for [Munsit (CNTXT AI)](https://munsit.com/) which posts WER 26.68 on Arabic dialects vs Whisper 36.86.

## Eval judge: Gemini 2.5 Pro (free, different from agent)

Brief explicitly says paid keys are not required to score well. Using a different model for the judge avoids the same-model-grading-itself failure mode.

## Vector store: LanceDB over Chroma

Modern, embedded, no separate service, cold-starts in <1s, uses Apache Arrow.

## Embeddings: Nemotron Embed VL 1B v2 (free via OpenRouter)

Multilingual including Arabic, free tier handles 35 documents in one indexing pass, no local install or GPU. OpenRouter is explicitly endorsed in the brief. Tradeoff: vendor lock to OpenRouter availability.

## Escalation engine: hard-coded regex, not an LLM

Deterministic. Auditable. Fast (sub-millisecond). Will never hallucinate a missed red flag in either direction.
- An LLM-based check could miss a red flag during a model regression. JAMA Pediatrics 2024 found ChatGPT-3.5 misdiagnosed 83/100 pediatric cases — strong evidence that LLMs are not yet trustworthy for safety-critical pediatric routing.
- Tradeoff: regex misses paraphrases ("she's not waking up much") that wouldn't fire under literal patterns. Mitigation: the LLM still has the system prompt rule to escalate; escalation_check is a *floor*, not a ceiling.

## Severity enum aligned to NICE traffic-light (green/amber/red)

Original draft used `info/caution/red_flag`. Renamed to align with the NICE NG143 reference standard, so anyone reviewing the code immediately recognises the source of authority.

## Data scope: 20 KB chunks, 15 products

Brief is ~5 hours. Original plan had 60 KB chunks + 50 products — theatrical scope hurts when a reviewer spot-checks a single chunk and finds it shallow. Shrunk to a tighter, higher-quality set biased toward the categories the eval cases actually exercise.

## What I cut and why

- **Wedge competitor table** — without probed transcripts of competitors on Khaleeji utterances, the table was rhetoric. Cut.
- **Multi-turn memory** — single-turn demonstrates the loop; conversational state adds complexity without rubric points.
- **Real product images** — synthetic catalog uses placeholders.
- **ElevenLabs / Lahajati TTS fallback** — Gemini 3.1 Flash Live's audio is acceptable for stretch demo. Toggle scaffolding can be added if Live's Khaleeji output is judged weak.
- **Native-speaker Arabic eval review** — flagged as the highest-leverage future work.
- **Postpartum mental-health module** — explicitly out of scope; refer to professional help.
- **Order-tracking integration** — would require Mumzworld backend access; called out as "what I'd build next."

## Voice scoped as Phase 7 stretch

Voice could have lived in the 5h core, but the brief grades on Production / Eval / Problem / Uncertainty / Tooling — voice quality earns nothing on those dimensions. Putting voice in core risks the preview SDK breaking and dragging eval rigor down. Putting voice as Phase 7 stretch (after core ships) means: (a) the rubric-graded path is complete and shippable before voice work begins, (b) voice failure is documentable not catastrophic, (c) the demo gets the emotional impact of a voice flow if Live cooperates.
