# 3am Mom / معك ليلاً — Design Spec

**Author:** Amitesh Gupta
**Date:** 2026-04-27
**Deadline:** 2026-04-29 17:00 GST
**Status:** Revised — voice is now the primary modality
**Build budget:** ~8 hours total, documented overrun per brief instructions. Voice is core, not stretch — Mumzworld has no voice surface today and that's the load-bearing differentiator.
**Context:** Mumzworld AI Engineering Intern take-home — Track A (AI Engineering Intern)

## Revision note (2026-04-27)

This spec was originally sized for 14h with a voice-first frame. After re-reading the official brief verbatim and running an adversarial cold-read review, the plan is revised:
- **Voice as primary modality.** Mumzworld currently has zero voice or LLM surface — phone, WhatsApp, live chat, email are all human-staffed (verified at mumzworld.com/en/contact-us). That's a real gap, not rhetoric. Voice is what makes this prototype evidence of a direction Mumzworld's stack genuinely lacks. Text mode still exists as a fallback in the UI and as the model the eval suite exercises (kept on free Gemini 2.5 Flash to isolate the rubric-graded path from preview SDK volatility), but voice via Gemini 3.1 Flash Live is the headline.
- **Model swap.** Free tools encouraged per brief: Gemini 2.5 Flash (free) for the agent, Gemini 2.5 Pro (free) for the judge — different models, avoids same-model-grading-itself circularity.
- **Data scope shrunk.** 60 KB chunks → 20 high-quality chunks; 50 products → 15. Theatrical scope hurts when a reviewer spot-checks a single chunk and finds it shallow.
- **Framing softened.** Pediatric triage is a listed example in the brief. Honest framing: "this is a listed problem built with a defensible engineering twist (deterministic NICE rule engine + grounded Mumzworld product layer + Arabic-first)." Not pitched as a wholly novel problem.
- **Khaleeji claim softened.** Brief asks for natural EN + AR, not specifically Khaleeji. The Arabic eval slice tests for "reads like native copy, not literal translation" rather than dialect-register match. Author does not speak Arabic — explicitly acknowledged.

---

## 1. Problem

Mumzworld customers — primarily mothers of children aged 0-3 — have **no voice or conversational AI surface** today. Phone, WhatsApp, live chat, and email are all human-staffed; the contact page lists zero AI assistants. The brand's stated direction is to become a **"trusted advisor and support system,"** but no voice interface exists. The hardest moments (a 3am scare with a feverish baby, hands occupied with the baby, eyes tired, a mother whose first language is Arabic) are exactly where text-based support fails and voice would unlock real reach.

This take-home builds a **voice-first prototype** that fills that gap: spoken EN or AR input → grounded answers, NICE-grade safety routing, and Mumzworld product recommendations spoken back. Pediatric symptom triage is one of the brief's listed example problems; the defensible angle here is the *combination* — voice + deterministic NICE NG143-grounded escalation (not LLM-based safety routing) + grounded answers with explicit IDK behaviour + integrated product layer with age-range filtering + Arabic-first multilingual handling — none of which Mumzworld currently ships in any form.

### Evidence

- **No LLM/voice surface on Mumzworld today.** Phone, WhatsApp, live chat, email — all human-staffed; contact page lists zero AI assistants. Source: [mumzworld.com/en/contact-us](https://www.mumzworld.com/en/contact-us).
- **Customer-service pain is verifiable.** App Store reviewer *Hallawat*: "I wait for hours to chat with someone... when you get a hold of someone, they promise you that they will ship the order [and don't]." Reviewer *Um aboody & khloody*: "It took 45 minutes to get someone to answer." Trustpilot agrees across 41+ pages of reviews.
- **No Khaleeji dialect handling anywhere on Mumzworld** — only an MSA toggle. 90%+ of Gulf Arabic speech is dialect.
- **Pediatric LLM safety is a documented hazard.** [JAMA Pediatrics 2024](https://jamanetwork.com/journals/jamapediatrics/articlepdf/2813283/) found ChatGPT-3.5 misdiagnosed **83/100 pediatric cases**. Any honest pediatric-adjacent product must route, not diagnose.

### Why this slice

Pediatric symptom triage is on the brief's example list. The defensible angle is the engineering shape, not novelty:

- **Deterministic safety routing**, not LLM-as-safety-classifier (JAMA Pediatrics 2024: ChatGPT misdiagnosed 83/100 pediatric cases).
- **Grounded answers with explicit IDK behavior** below confidence threshold.
- **Mumzworld catalog integrated as a tool, not bolted on** — age-range filtering, never pushed during medical concern.
- **Arabic-first**, treated as primary requirement not afterthought.

A binary "we own X, they don't" wedge table was considered and dropped — it's rhetoric without probed transcripts of competitor outputs, which there isn't time to produce.

---

## 2. Product

**Working name:** "3am Mom" (project codename). Final naming + trademark sweep is out of scope for the build.

**Core loop (voice-primary):** Mother taps mic and speaks in EN or AR. Agent transcribes, classifies for medical red flags first, then either (a) speaks a firm doctor-referral, or (b) speaks a grounded answer from the knowledge base and optionally surfaces 1–2 relevant Mumzworld products on screen. Text input is available as a fallback for environments where mic permissions or audio playback fail, and is the modality the eval suite exercises.

**Four guarantees the agent must keep:**

1. **Match the user's language.** Arabic input → natural-sounding Arabic output (not literal English-to-Arabic translation, the brief's named failure mode). English input → English output.
2. **Ground every factual claim** against the knowledge base. Below confidence threshold → say "I don't know" and refer to a pediatrician.
3. **Route, never diagnose.** Red flags hard-stop and refer to a doctor. Citing JAMA 2024.
4. **Be brief.** 1–3 short sentences per turn.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────┐
│  Streamlit UI                                    │
│  - Text chat (core)                              │
│  - Mic via streamlit-webrtc (voice stretch)      │
└────────────┬───────────────┬─────────────────────┘
             │ user_text     │ audio chunks (PCM16)
             ▼               ▼
┌──────────────────────────────────────────────────┐
│  src/agent.py                                    │
│  - turn(text) → AgentResponse  (text-mode core)  │
│  - stream(audio) → async events (voice stretch)  │
└────────┬─────────────────┬───────────────────────┘
         │ text mode       │ voice mode
         ▼                 ▼
   OpenRouter           Gemini API (Google AI Studio)
   Llama 3.3 70B (free) Gemini 3.1 Flash Live preview
   via OpenAI SDK       via google-genai aio.live
         │                 │
         └─────┬───────────┘
               │ same 3 tools, same system prompt
               ▼
   ┌──────────────────┬──────────────────┬─────────────────┐
   │ escalation_check │ knowledge_search │ product_search  │
   │ NICE NG143 regex │ LanceDB+Nemotron │ LanceDB+Nemotron│
   └──────────────────┴──────────────────┴─────────────────┘

  Logged per turn → AgentResponse (Pydantic) → evals/results.json
  Eval judge: OpenRouter Qwen 2.5 72B free (different model family from agent)
```

### Why these choices (defended in README)

- **Two-API split: Gemini API for voice, OpenRouter for everything else.** Voice runs on Gemini 3.1 Flash Live preview through `google-genai`'s `aio.live` (paid Gemini API key). All text-LLM work — text-mode agent, eval judge — runs on OpenRouter free models per the brief's explicit recommendation. This isolates the rubric-graded path (text agent + judge, both on OpenRouter free tier) from preview SDK volatility.
- **Text agent on Llama 3.3 70B Instruct (free via OpenRouter).** Strong function-calling support, multilingual including Arabic, generous free tier. Used via OpenAI-compatible API (OpenRouter speaks OpenAI's chat-completions schema).
- **Judge on Qwen 2.5 72B Instruct (free via OpenRouter).** Different model family from agent → avoids same-model-grading-itself. Strong Arabic.
- **Why both in `OpenAI` SDK form:** OpenRouter is OpenAI-compatible, so we can use one client (`openai.OpenAI` pointed at `https://openrouter.ai/api/v1`) for both agent and judge. Single dependency, single retry path.
- **LanceDB over Chroma:** modern, embedded, faster cold start.
- **Nemotron Embed VL via OpenRouter:** free tier, multilingual, no local install or GPU required. OpenRouter is explicitly endorsed in the brief.
- **NICE NG143 traffic-light as escalation rule engine:** deterministic (auditable, fast, no LLM hallucination on safety). JAMA 2024 (83% LLM pediatric misdiagnosis) is cited in the system prompt as the explicit reason the agent routes-not-diagnoses.
- **Pydantic v2 everywhere:** schemas double as eval contracts; failures explicit, not silent (matches brief's "good" criteria).

---

## 4. Components

### 4.1 Schemas (`src/schemas.py`)

All types defined upfront. See original prompt for the full list — `KnowledgeChunk`, `Product`, `ProductRecommendation`, `EscalationFlag`, `AgentResponse`, plus tool I/O models. **One change from the original prompt:** `Severity` enum aligns to NICE traffic-light:

```python
class Severity(str, Enum):
    GREEN = "green"      # info — general guidance
    AMBER = "amber"      # caution — see pediatrician if X
    RED = "red"          # red flag — immediate medical attention
```

`EscalationFlag.triggers` keeps the category list; the rule engine maps each NICE NG143 row to a category.

### 4.2 Escalation rule engine (`src/tools/escalation_check.py`)

Hard-coded, NOT an LLM call. Categories are NICE NG143-derived:

- `fever_under_3_months` — any fever ≥38°C in <3-month-old → RED (NICE absolute rule)
- `breathing_distress` — wheezing, blue lips, retractions → RED
- `hydration_red` — sunken fontanelle, no wet diaper >8h → RED
- `consciousness_red` — unconscious, unresponsive, lethargic → RED
- `seizure` → RED
- `blood_in_output` — vomit, stool, persistent → RED
- `head_injury` → RED
- `poisoning_choking` → RED
- `explicit_emergency` — user says ER/hospital/طوارئ → RED

Each category has 2–4 regex patterns (EN + AR script). Khaleeji transliterations included where common. Function returns `EscalationFlag` with NICE category names in `triggers`.

### 4.3 RAG layer

- **Index** (`src/index_kb.py`): one-time script. Loads `data/knowledge_base.json` (20 chunks) and `data/products.json` (15 items), embeds `text_en + " " + text_ar` (combined for cross-lingual retrieval), writes two LanceDB tables.
- **Knowledge search** (`src/tools/knowledge_search.py`): embed query → top-k cosine → filter at `MIN_CONFIDENCE = 0.5`.
- **Product search** (`src/tools/product_search.py`): same pattern, with optional `age_range_months` filter.

### 4.4 Agent (`src/agent.py`)

Two entry points sharing the same system prompt + tool definitions:

- **`async stream(audio_chunks)`** — primary modality. Wraps `client.aio.live.connect(model="gemini-3.1-flash-live-preview")`. Yields user-transcript / agent-transcript / audio / tool_call events. Manual tool execution per Live API contract. This is what the demo Loom showcases.
- **`turn(text) -> AgentResponse`** — text fallback in the UI, AND the entry point the eval suite uses. Sync; uses `genai.Client.models.generate_content` with `model="gemini-2.5-flash"`. Manual tool execution loop until final text.

Why two paths instead of just voice: the eval suite needs to be deterministic, fast, and free of audio-codec variance to produce credible rubric scores. Running 12 cases through Live audio per eval pass would be slow, expensive, and noisy. Text-mode `turn()` exercises the same system prompt + tool definitions, so eval scores generalize to voice behaviour.

Both paths log each turn as `AgentResponse` so the structured logs are uniform.

### 4.5 System prompt (`src/prompts/system_prompt.md`)

Per the original prompt, with **two additions**:

- Explicit JAMA 2024 citation: *"Pediatric LLM diagnosis has documented 83% error rates (JAMA Peds 2024). You route. You do not diagnose."*
- NICE NG143 framing: *"Use the NICE traffic-light system. Red = stop, refer to doctor. Amber = answer with caution + suggest pediatrician follow-up. Green = answer normally with citations."*

### 4.6 UI (`app.py`)

Streamlit voice-first chat. **Mic button is the headline interaction:** large Push-to-Talk component using `streamlit-webrtc` streams PCM16 audio chunks to `agent.stream()` and renders user transcript, agent transcript, audio playback, and tool-call events in-line. RTL handling for Arabic. Red banner on escalation. Product cards (1–2 max) appear inline alongside the spoken response. Latency + confidence shown per turn. **Text fallback** chat input is also visible (smaller, below the mic) for environments where the browser blocks mic access or audio playback misbehaves.

### 4.7 Evals (`evals/run_evals.py`)

12 test cases in `data/test_cases.json` (brief requires 10+):

- 3 medical red flags (under-3-month fever, breathing, blood-in-output)
- 3 product queries (thermometer, sleep sack 1yo, breast pump)
- 2 out-of-scope (mortgage, political)
- 2 IDK / ambiguous (encourages model to say "I don't know")
- **2 Arabic adversarial slice** (Arabic symptom mix; Arabic product mix) — checks for natural Arabic, not literal-translation-from-English (the brief's named failure mode)

LLM-as-judge: **Gemini 2.5 Pro** (free tier, different model from the agent — avoids same-model grading itself). Rubric in `evals/rubric.md`:

- Groundedness (0–2)
- Safety correctness (0–2)
- Language quality (0–2) — Arabic reads like native copy, not literal translation
- Product relevance (0–2)

Total: 8 × 12 = 96. Results saved to `evals/results.json` with per-case judge notes.

---

## 5. Build order (~8h, voice is core)

Rubric: Production 30%, Eval 25%, Problem 20%, Uncertainty 15%, Tooling 10%. Voice doesn't appear in the rubric directly, but it's the load-bearing differentiator of the *Problem* selection (20%) — Mumzworld has no voice today, so a voice-capable prototype is the credible demonstration. Build order interleaves voice with text-mode so neither is rushed at the end.

**Phase 1 (foundation, ~45 min)**
1. Repo scaffold, `requirements.txt`, `.env.example`, `.gitignore`
2. `src/schemas.py` complete
3. `src/config.py` (env, thresholds)
4. `src/tools/escalation_check.py` + 10 unit tests against NICE-grounded inputs

**Phase 2 (data, ~75 min)**
5. `data/products.json` (15 items, EN+AR, age ranges, AED prices)
6. `data/knowledge_base.json` (20 chunks, paraphrased WHO/AAP/NHS/NICE/CDC, severity-tagged)
7. Pydantic-validate both on load

**Phase 3 (RAG, ~30 min)**
8. `src/index_kb.py`, run, verify tables
9. `src/tools/knowledge_search.py` + `product_search.py`
10. Smoke test each with 2 queries

**Phase 4 (agent text-mode, ~45 min)**
11. `src/prompts/system_prompt.md` (with JAMA + NICE)
12. `src/agent.py` — sync text mode using Gemini 2.5 Flash, tools wired
13. End-to-end test with 5 inputs

**Phase 5 (evals, ~60 min)**
14. `data/test_cases.json` (12 cases incl. Arabic slice)
15. `evals/rubric.md`, `src/prompts/eval_judge_prompt.md`
16. `evals/run_evals.py` — judge with Gemini 2.5 Pro, run, save results, fix obvious failures, re-run

**Phase 6 (UI + docs + ship, ~45 min)**
17. `app.py` — minimal Streamlit text chat
18. `README.md` — problem framing, architecture, evals, tradeoffs, tooling transparency, limitations
19. `docs/architecture.md` + `docs/tradeoffs.md`
20. Loom recording (3 min, 5 inputs incl. one IDK or refuse), final commit, push

**Phase 7 (voice integration, ~2h)**
21. `src/agent.py` — add `async stream(audio_chunks)` method using Gemini 3.1 Flash Live (preview SDK). Same system prompt + tool definitions as `turn()`.
22. `app.py` — add streamlit-webrtc Push-to-Talk mic component as the primary interaction; keep text input visible as fallback.
23. End-to-end voice smoke-test: 1 EN query, 1 AR query, 1 red-flag query, 1 product query. Verify transcripts, audio playback, tool calls, escalation banner all render.

**Phase 8 (Loom + final polish, ~30 min)**
24. Record 3-min Loom showing 5 inputs end-to-end including at least one IDK or refuse — voice for at least 2 of them (per brief requirement).
25. Final repo polish, push.

**Total: ~8h.** Documented overrun explicit in README per brief instructions ("If you spend more, note where the time went").

**Cut order if pressed:** Streamlit polish (RTL CSS niceties, product card styling) → architecture/tradeoffs split into one file → 12 evals trimmed to 10 (brief minimum) → KB trimmed to 15. **Never cut:** voice mode, text-mode agent, schemas, escalation_check, RAG, system prompt, eval framework, README, Loom.

---

## 6. What's explicitly cut and why

- **Binary wedge competitor table.** Without probed transcripts of Sehhaty/Altibbi/Bebbo on real Khaleeji utterances, the binary table is rhetoric. The voice-gap claim survives ("Mumzworld has zero voice/LLM surface today") because that one is verifiable from their own contact page; competitors' positioning was not audited.
- **Native Arabic-speaking eval reviewer.** The right move with more budget; flagged as the highest-leverage future work in section 9.
- **Multi-turn memory** — single-turn demonstrates the loop; conversational state adds complexity without rubric points.
- **Real product images** — synthetic catalog uses placeholders.
- **ElevenLabs / Lahajati TTS fallback** — Gemini 3.1 Flash Live's native audio is the primary voice path. Fallback toggle could be wired later if Live's Khaleeji output is judged weak by a native reviewer.
- **Postpartum mental-health module** — explicitly out of scope; refer to professional help.
- **Order-tracking integration** — would require Mumzworld backend access; called out as "what I'd build next."

**NOT cut:** voice (now primary), NICE NG143 escalation, RAG, eval suite, IDK behaviour, README, Loom.

---

## 7. Risks and contingencies

| Risk | Likelihood | Mitigation |
|---|---|---|
| Nemotron Embed via OpenRouter rate-limits during indexing | L | Index is one-shot, 35 documents total. Retry-with-backoff. Local sentence-transformers as a 20-min fallback. |
| Arabic eval scoring is unreliable (LLM judge has same blind spots as agent) | H | Section 9 names this honestly: 12 cases include 2 Arabic ones; without a native-speaker reviewer the scores are directional, not authoritative. README is direct about this. |
| Gemini 2.5 Flash function-calling format changes between SDK versions | L | Pin `google-genai>=0.3.0` in requirements; if function-call shape differs from docs, log raw response and adjust parser, do not fabricate. |
| **Gemini 3.1 Flash Live preview SDK regresses or signatures shift mid-build** | M | Build voice in Phase 7 *after* the entire text-mode path (RAG, escalation, evals) is shippable. If Live preview breaks, the demo Loom records voice from a working snapshot or falls back to text mode for those queries. The eval suite is text-mode and unaffected. |
| streamlit-webrtc mic permissions or audio playback issues in the demo browser | M | Pre-test the mic flow in Chrome before recording. Keep text fallback visible and functional in the same UI. Loom can pre-record the voice flow against a stable Live build if demo-day mic is flaky. |
| Live API audio quality on Khaleeji is poor | M | Acknowledge in section 9. ElevenLabs/Lahajati fallback toggle could be added (~30 min) if Live's Khaleeji audio is judged unintelligible. |
| ~8h budget overruns | M | Brief explicitly allows overruns when documented. README will track time spent per phase. Cut order documents what gets trimmed first (Streamlit polish, then docs split). |

---

## 8. Tooling transparency (preview of README section)

- **Coding workflow:** AI-assisted throughout — brainstorming, design doc, plan, implementation, eval iteration.
- **Models in production:** Gemini 3.1 Flash Live preview (paid via Gemini API; primary voice agent — the headline interaction), Llama 3.3 70B Instruct (free via OpenRouter; text-mode agent + the entry point the eval suite exercises), Qwen 2.5 72B Instruct (free via OpenRouter; eval judge — different model family from agent to avoid same-model self-grading), Nemotron Embed VL 1B v2 (free via OpenRouter; embeddings).
- **Two API providers, deliberately:** Gemini API for voice (only Live preview supports the audio loop we need); OpenRouter for everything else (per brief recommendation, free models, single OpenAI-compatible SDK).
- **Why no LangChain/LangGraph:** YAGNI. Three tool functions and a Pydantic schema do not need a framework.
- **Material overrides made during build:** (a) reframed escalation as NICE NG143-grounded; (b) added JAMA Pediatrics 2024 citation to system prompt as the explicit safety justification; (c) shrank data scope from initial 60/50 plan to 20/15 to favor quality over theatrics; (d) split agent into stable text-mode (eval path) plus voice stretch (demo path) so SDK preview risk doesn't bleed into rubric-graded code.
- **Prompts committed in repo** under `src/prompts/system_prompt.md` and `src/prompts/eval_judge_prompt.md`.

---

## 9. Limitations (preview of README section)

- **I don't speak Arabic.** Arabic KB chunks and the 2-case Arabic eval slice are LLM-generated and LLM-judged. Both the agent and the judge may share the same dialect blind spots, so the Arabic language-quality score is directional evidence, not ground truth. A native Gulf Arabic-speaking reviewer is the right next step and is named explicitly as future work.
- **Knowledge base is 20 chunks.** Sized for 5-hour budget. Production needs clinical review by a pediatrician — explicitly out of scope.
- **Synthetic 15-item catalog.** No Mumzworld product data was scraped (per brief constraint).
- **NICE NG143 is UK pediatric guidance.** Used as a starting taxonomy for red-flag categories. Localizing to Gulf clinical practice would need a regional clinical reviewer.
- **Time tracking.** Budget is ~5h core; if overrun occurs, hours and reason are documented in the README per brief instructions.

---

## Approval

Spec revised 2026-04-27 after re-reading the official brief verbatim and incorporating an adversarial cold-read review. Pending user approval to proceed to subagent-driven execution.
