"""3am Mom agent.

Two entry points:
- turn(text)      → OpenRouter (Llama 3.3 70B free) — text mode + eval entry point
- stream(audio)   → Gemini 3.1 Flash Live preview — voice mode (added in Phase 7)

Both share the same system prompt and tool semantics. Voice and text behaviour
generalise because the system prompt is identical; the eval suite exercises the
text-mode path, which is more deterministic and free of audio-codec variance.
"""
from __future__ import annotations
import json
from typing import Any

from openai import OpenAI

from google import genai
from google.genai import types as gtypes

from src.config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, AGENT_MODEL, PROMPTS_DIR,
    GOOGLE_API_KEY, LIVE_MODEL,
)
from src.schemas import (
    AgentResponse, Language,
    EscalationCheckInput, KnowledgeSearchInput, ProductSearchInput,
)
from src.tools.escalation_check import check_escalation
from src.tools.knowledge_search import search_knowledge
from src.tools.product_search import search_products


SYSTEM_PROMPT = (PROMPTS_DIR / "system_prompt.md").read_text()


GEMINI_TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "escalation_check",
        "description": (
            "Classify user input against NICE NG143 pediatric red-flag categories. "
            "Call this FIRST whenever the user mentions any symptom or medical-adjacent question."
        ),
        "parameters": {
            "type": "object",
            "properties": {"user_text": {"type": "string"}},
            "required": ["user_text"],
        },
    },
    {
        "name": "knowledge_search",
        "description": "Retrieve grounded parenting/baby-care chunks from the curated knowledge base.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "product_search",
        "description": "Find Mumzworld products relevant to the user's need.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "age_range_months_low": {"type": "integer"},
                "age_range_months_high": {"type": "integer"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]


# OpenAI-compatible tool declarations (OpenRouter speaks this schema)
OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "escalation_check",
            "description": (
                "Classify user input against NICE NG143 pediatric red-flag categories. "
                "Call this FIRST whenever the user mentions any symptom or asks a medical-adjacent question."
            ),
            "parameters": {
                "type": "object",
                "properties": {"user_text": {"type": "string"}},
                "required": ["user_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": (
                "Retrieve grounded parenting/baby-care chunks from the curated knowledge base. "
                "Use for any factual question about feeding, sleep, illness, milestones, postpartum, safety."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 3},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "product_search",
            "description": (
                "Find Mumzworld products relevant to the user's need. Only call after answering the question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "age_range_months_low": {"type": "integer"},
                    "age_range_months_high": {"type": "integer"},
                    "max_results": {"type": "integer", "default": 2},
                },
                "required": ["query"],
            },
        },
    },
]


def _detect_language(text: str) -> Language:
    has_arabic = any("؀" <= ch <= "ۿ" for ch in text)
    if not has_arabic:
        return Language.EN
    return Language.AR_KHALEEJI  # treat Arabic input as Khaleeji-target by default


def _execute_tool(name: str, args: dict) -> dict:
    if name == "escalation_check":
        out = check_escalation(EscalationCheckInput(**args))
        return out.model_dump()
    if name == "knowledge_search":
        out = search_knowledge(KnowledgeSearchInput(**args))
        return out.model_dump()
    if name == "product_search":
        lo = args.pop("age_range_months_low", None)
        hi = args.pop("age_range_months_high", None)
        age_range = (lo, hi) if lo is not None and hi is not None else None
        out = search_products(ProductSearchInput(**args, age_range_months=age_range))
        return out.model_dump()
    return {"error": f"unknown tool: {name}"}


class Agent:
    def __init__(self, model: str = AGENT_MODEL):
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY not set in .env")
        self._client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self._model = model
        # Phase 7 will lazy-init a google-genai client here for the voice path.
        self._gemini_client = None

    def turn(self, user_text: str) -> AgentResponse:
        """One synchronous text turn. Loops until the model emits a final assistant text."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]
        kb_used: list[dict] = []
        prods_used: list[dict] = []
        escalation: dict | None = None

        for _ in range(6):  # cap on tool-call rounds
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=OPENAI_TOOLS,
                tool_choice="auto",
                # OpenRouter forwards extra fields; these help with attribution.
                extra_headers={
                    "HTTP-Referer": "https://github.com/singlaamitesh/mumzworld-3am-mom",
                    "X-Title": "3am Mom",
                },
            )
            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None) or []

            if tool_calls:
                # Echo the assistant turn (with tool_calls) into history per OpenAI spec.
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })
                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json.JSONDecodeError:
                        args = {}
                    tool_out = _execute_tool(name, args)
                    if name == "knowledge_search":
                        kb_used = tool_out.get("chunks", [])
                    elif name == "product_search":
                        prods_used = tool_out.get("recommendations", [])
                    elif name == "escalation_check":
                        escalation = tool_out.get("flag")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": json.dumps(tool_out, ensure_ascii=False),
                    })
                continue

            final_text = (msg.content or "").strip()
            user_lang = _detect_language(user_text)
            resp_lang = _detect_language(final_text) if final_text else user_lang
            confidence = 0.9 if kb_used else (1.0 if escalation and escalation.get("triggered") else 0.5)
            return AgentResponse(
                user_input_text=user_text,
                user_input_language=user_lang,
                response_language=resp_lang,
                response_text=final_text,
                knowledge_chunks_used=kb_used,
                products_recommended=prods_used,
                escalation=escalation,
                confidence=confidence,
                in_scope=True,
            )

        # Fallback if we hit the loop cap
        return AgentResponse(
            user_input_text=user_text,
            user_input_language=_detect_language(user_text),
            response_language=Language.EN,
            response_text="I'm sorry, I couldn't formulate an answer. Please try again.",
            confidence=0.0,
            in_scope=False,
        )

    async def stream(self, audio_chunks):
        """Async live audio session. audio_chunks is an async iterable of PCM16 bytes at 16kHz.

        Yields dicts of one of these shapes:
          {'type': 'transcript_user',  'text': str}
          {'type': 'transcript_agent', 'text': str}
          {'type': 'audio',            'data': bytes}    # PCM16 24kHz from Gemini Live
          {'type': 'tool_call',        'name': str, 'args': dict}
          {'type': 'tool_done',        'name': str, 'output': dict}
        """
        import asyncio

        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY not set in .env (required for voice mode)")

        # Lazy-init the Gemini client only when voice is actually used.
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

        gemini_tool = gtypes.Tool(function_declarations=GEMINI_TOOL_DECLARATIONS)
        live_config = gtypes.LiveConnectConfig(
            response_modalities=[gtypes.Modality.AUDIO],
            system_instruction=gtypes.Content(parts=[gtypes.Part(text=SYSTEM_PROMPT)]),
            tools=[gemini_tool],
            input_audio_transcription=gtypes.AudioTranscriptionConfig(),
            output_audio_transcription=gtypes.AudioTranscriptionConfig(),
        )

        async with self._gemini_client.aio.live.connect(model=LIVE_MODEL, config=live_config) as session:
            async def _send_audio():
                async for chunk in audio_chunks:
                    await session.send_realtime_input(
                        audio=gtypes.Blob(data=chunk, mime_type="audio/pcm;rate=16000"),
                    )

            send_task = asyncio.create_task(_send_audio())
            try:
                async for message in session.receive():
                    if getattr(message, "tool_call", None):
                        for fc in message.tool_call.function_calls:
                            yield {"type": "tool_call", "name": fc.name, "args": dict(fc.args or {})}
                            tool_out = _execute_tool(fc.name, dict(fc.args or {}))
                            await session.send_tool_response(function_responses=[
                                gtypes.FunctionResponse(id=fc.id, name=fc.name, response=tool_out),
                            ])
                            yield {"type": "tool_done", "name": fc.name, "output": tool_out}
                    if getattr(message, "server_content", None):
                        sc = message.server_content
                        if getattr(sc, "input_transcription", None) and sc.input_transcription.text:
                            yield {"type": "transcript_user", "text": sc.input_transcription.text}
                        if getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                            yield {"type": "transcript_agent", "text": sc.output_transcription.text}
                        if getattr(sc, "model_turn", None) and sc.model_turn.parts:
                            for p in sc.model_turn.parts:
                                if getattr(p, "inline_data", None) and p.inline_data.data:
                                    yield {"type": "audio", "data": p.inline_data.data}
            finally:
                send_task.cancel()


# ---------------------------------------------------------------------------
# Voice helpers — used by Streamlit's st.audio_input flow (single-shot)
# ---------------------------------------------------------------------------

def wav_to_pcm16_16k(wav_bytes: bytes) -> bytes:
    """Convert a WAV (any sample rate / channel count / sample width) to mono PCM16 at 16kHz.

    st.audio_input returns WAV bytes; Gemini Live wants PCM16 at 16kHz mono.
    """
    import io
    import wave
    import audioop

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        n_channels = w.getnchannels()
        sample_width = w.getsampwidth()
        framerate = w.getframerate()
        frames = w.readframes(w.getnframes())

    # Stereo → mono
    if n_channels == 2:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)

    # Any sample width → 16-bit
    if sample_width != 2:
        frames = audioop.lin2lin(frames, sample_width, 2)

    # Any rate → 16kHz
    if framerate != 16000:
        frames, _ = audioop.ratecv(frames, 2, 1, framerate, 16000, None)

    return frames


def pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap PCM16 mono audio in a WAV header (Gemini Live returns PCM16 at 24kHz)."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm_bytes)
    return buf.getvalue()


def turn_voice(agent: "Agent", wav_bytes: bytes) -> dict:
    """One-shot voice turn for Streamlit. Sends a recorded WAV clip, returns
    a dict with user transcript, agent transcript, response audio (WAV), and
    any tool-call summaries.

    Synchronous wrapper around an internal asyncio session so Streamlit can
    just call it without managing event loops.
    """
    import asyncio

    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set in .env (required for voice mode)")

    pcm_in = wav_to_pcm16_16k(wav_bytes)

    if agent._gemini_client is None:
        agent._gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

    gemini_tool = gtypes.Tool(function_declarations=GEMINI_TOOL_DECLARATIONS)
    live_config = gtypes.LiveConnectConfig(
        response_modalities=[gtypes.Modality.AUDIO],
        system_instruction=gtypes.Content(parts=[gtypes.Part(text=SYSTEM_PROMPT)]),
        tools=[gemini_tool],
        input_audio_transcription=gtypes.AudioTranscriptionConfig(),
        output_audio_transcription=gtypes.AudioTranscriptionConfig(),
    )

    async def _run():
        user_t: list[str] = []
        agent_t: list[str] = []
        audio_chunks: list[bytes] = []
        tool_log: list[dict] = []

        async with agent._gemini_client.aio.live.connect(model=LIVE_MODEL, config=live_config) as session:
            # Send the entire clip in 20ms slices to look like real-time audio,
            # then mark the user's turn complete so the model responds.
            slice_bytes = int(16000 * 0.02) * 2  # 20ms of PCM16 at 16kHz
            for i in range(0, len(pcm_in), slice_bytes):
                chunk = pcm_in[i : i + slice_bytes]
                if not chunk:
                    break
                await session.send_realtime_input(
                    audio=gtypes.Blob(data=chunk, mime_type="audio/pcm;rate=16000"),
                )
            # End of user turn (server-side VAD also helps but be explicit).
            try:
                await session.send_realtime_input(audio_stream_end=True)
            except TypeError:
                # SDK variant: send_client_content with turn_complete
                await session.send_client_content(turn_complete=True)

            # Drain server messages until the model signals turn-complete.
            async for message in session.receive():
                if getattr(message, "tool_call", None):
                    for fc in message.tool_call.function_calls:
                        out = _execute_tool(fc.name, dict(fc.args or {}))
                        tool_log.append({"name": fc.name, "args": dict(fc.args or {}), "output": out})
                        await session.send_tool_response(function_responses=[
                            gtypes.FunctionResponse(id=fc.id, name=fc.name, response=out),
                        ])
                if getattr(message, "server_content", None):
                    sc = message.server_content
                    if getattr(sc, "input_transcription", None) and sc.input_transcription.text:
                        user_t.append(sc.input_transcription.text)
                    if getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                        agent_t.append(sc.output_transcription.text)
                    if getattr(sc, "model_turn", None) and sc.model_turn.parts:
                        for p in sc.model_turn.parts:
                            if getattr(p, "inline_data", None) and p.inline_data.data:
                                audio_chunks.append(p.inline_data.data)
                    if getattr(sc, "turn_complete", False):
                        break

        return {
            "user_transcript": "".join(user_t).strip(),
            "agent_transcript": "".join(agent_t).strip(),
            "audio_wav": pcm16_to_wav(b"".join(audio_chunks), sample_rate=24000) if audio_chunks else b"",
            "tool_log": tool_log,
        }

    return asyncio.run(_run())
