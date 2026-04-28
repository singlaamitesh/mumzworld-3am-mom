# Loom recording script — 3 minutes, 5 inputs

**Total target: 3:00.** Pre-record dry run once, then record for real.

---

## ☑️ Pre-flight (do all 6 before hitting record)

```bash
# 1. Clean state — close all other tabs
# 2. Voice server up
source .venv/bin/activate
uvicorn voice.server:app --port 8000 --log-level warning &

# 3. Hard reload http://localhost:8000 (Cmd+Shift+R)
# 4. Test mic permission once (tap the orb, say "hello", end session)
# 5. In a separate tab, open these for screen-share:
#    a. http://localhost:8000  ← voice UI
#    b. README.md (rendered on GitHub or in a markdown preview)
#    c. evals/results.json (in your editor)
# 6. In the Mac menu bar, set Do Not Disturb. Silence Slack, email, Discord.
```

**Loom settings:**
- Cam: bottom-right circle (small, not distracting)
- Audio: external mic if you have one; otherwise built-in is fine
- Resolution: 1080p

**Recording position:** Voice tab as the main focus. Switch to README/results.json for ~5s each at the eval moment.

---

## 🎬 Verbatim script (read steady — don't rush)

### [0:00–0:08] · Hook
**[Cam-only, voice tab visible]**
> "Hi, I'm Amitesh. I built a voice-first parenting copilot for Mumzworld customers. Three minutes — five real demos, then how I judged my own work."

### [0:08–0:30] · Problem framing
**[Voice UI on screen, scroll once over README]**
> "Mumzworld serves millions of mothers across the GCC. Their support is human-staffed, slow — App Store reviews quote 45-minute waits, and there's zero voice surface today. The hardest moment for a mom is 3am with a feverish baby, hands occupied, eyes tired, often switching between Arabic and English. That's the gap this fills."

### [0:30–0:55] · Architecture in one breath
**[Voice UI, point at the orb / pink interface]**
> "Voice runs on Gemini 3.1 Flash Live preview. Text and the eval judge run on free OpenRouter models, deliberately different families to avoid same-model self-grading. The safety layer is regex against NICE NG143 — *not* an LLM — because JAMA Pediatrics found ChatGPT misdiagnoses 83% of pediatric cases. So the agent **routes**, it does not diagnose."

### [0:55–1:15] · Demo 1 — Product query (English)
**[Tap the orb, allow mic, say:]**
> "What thermometer should I buy for my baby?"

**[Wait for response. Agent should call knowledge_search + product_search, recommend infrared forehead thermometer, drop product cards.]**

**[Voice-over while it answers:]**
> "It pulls one chunk from a 20-item knowledge base, calls product_search with 'infrared forehead thermometer', returns a real catalog match — name, price in AED, English and Arabic descriptions."

### [1:15–1:40] · Demo 2 — Red flag (Arabic / Khaleeji)
**[Stay in same session. Speak in Arabic — read from screen if needed:]**
> "إبني عمره ثمن شهور صار حرارته ثمان وثلاثين ونص ما يبي يرضع"

**[Wait. Escalation banner should appear at top in red. Agent speaks back in Khaleeji-style Arabic.]**

**[Voice-over:]**
> "Escalation check fires immediately — the regex caught the fever and feeding refusal pattern. Red banner names the NICE NG143 category. Agent matches the user's language, refuses to give medical advice, refers to emergency."

### [1:40–2:00] · Demo 3 — Out of scope
**[Stay in session. Type into the text box at bottom, or speak:]**
> "What's the best mortgage rate in the UAE?"

**[Wait. Agent should politely refuse and redirect.]**

**[Voice-over:]**
> "Out of scope. One sentence, polite, redirects to a bank. No fabrication, no hallucinated numbers."

### [2:00–2:20] · Demo 4 — Honest IDK *(brief requires this)*
**[Stay in session. Type or speak:]**
> "Should I give my baby gold leaf in her milk?"

**[Wait. Agent should say it doesn't have specific guidance, suggest pediatrician.]**

**[Voice-over:]**
> "Brief explicitly required at least one input where the model expresses uncertainty. Here it doesn't fabricate a benefit, doesn't confirm gold leaf — says it's not aware and suggests a pediatrician."

### [2:20–2:35] · Demo 5 — Tool discipline
**[Type or speak:]**
> "How often should I feed my newborn?"

**[Wait. Agent calls knowledge_search but NOT product_search — proves the recently-fixed prompt rule that says don't push products on guidance questions.]**

**[Voice-over:]**
> "Notice — no product cards. Brief was clear: don't push products on emotional or guidance-shaped questions. The system prompt enforces that explicitly. Earlier in the build the agent recommended shampoo for a food query — fixed by tightening the threshold and the rule."

### [2:35–2:55] · Eval rigor + honest failures
**[Switch to README — Eval results section, then Honest failures]**
> "12 test cases — red flags, products, out-of-scope, IDK, and Arabic mixed. Judged by a different model family from the agent: GPT-OSS-120B answers, GLM-4.5-Air grades. **Total: 78 out of 96, 81 percent.** Three named failures in the README — the moon-cheese IDK fabricated instead of refusing, English fever escalates correctly but drifts to Arabic, judge flaked on one out-of-scope case. All in the repo, nothing hidden."

### [2:55–3:00] · Tooling transparency + close
**[Back to the voice UI]**
> "AI-assisted build throughout, per brief permission. Free OpenRouter for everything except voice. Repo, spec, plan, decision log all in `docs/superpowers/`. Thanks for watching."

**[End recording. Stop the orb session.]**

---

## ⏱️ Timing notes

- If a live demo stalls or the model is slow on a free-tier latency spike: **don't wait for it on camera** — speak the voice-over over the loading state. The reviewer cares about the architecture and the framing, not whether each turn lands in 4s vs 8s.
- If voice fails entirely on the day: switch to the text input at the bottom of the same UI. The narration script still works — just say *"voice mode is using a preview SDK that's been flaky today; same backend, same tools, falling back to text"*.
- Total **~3:00**. If you run over to 3:15 it's fine. If you hit 3:30+ you're rambling — cut a demo.

---

## 🚨 What to do if something breaks live

| Symptom | What to do | What to say |
|---|---|---|
| Mic permission denied | Click address bar lock icon → reset → reload | "let me reset the mic permission" |
| Voice connects then immediately ends | Server log, hard reload | use text input for that demo |
| Agent loops on same tool call | Wait 8s; if no response, type next query | mention "free-tier latency spike, switching to text" |
| Audio playback choppy | Don't fix — keep going | nothing — the reviewer hears voice from your Loom mic anyway |
| Streamlit UI broken | You aren't using Streamlit in this Loom — voice UI is at `:8000` | n/a |

---

## 🎯 What the reviewer should remember after watching

1. **The two-API split is intentional**, defended out loud
2. **NICE + JAMA + regex** is the safety story, named in 8 seconds
3. **5 demos covered all rubric dimensions**: production quality, eval rigor, problem selection, uncertainty handling, tooling transparency
4. **78/96 is honest** — failures named in the README before they had to dig
5. **Free tools throughout**, paid only where it has to be (Live preview)

If the reviewer says *"I want to talk to this person about this for an hour"* — that's the win condition for the Loom.
