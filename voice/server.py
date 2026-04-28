"""FastAPI WebSocket server: bridges the browser mic to Gemini 3.1 Flash Live.

Flow per session:
  1. Browser opens WS connection.
  2. Server opens Gemini Live session with our system prompt + 3 tools.
  3. Browser streams PCM16 16kHz mono audio chunks as binary frames.
  4. Server forwards them to Live (server-side VAD detects speech end).
  5. Live emits events: input_transcription, output_transcription, model audio,
     tool_call. Server forwards as JSON (text frames) + binary (audio frames).
  6. Tool calls are executed locally and the result is returned to Live.
  7. Auto-end:
       - If browser disconnects → close session.
       - If model finishes its turn AND no new user audio for IDLE_TIMEOUT_S
         → server sends {"type":"session_ended","reason":"idle"} and closes.
       - If session has been alive for HARD_LIMIT_S → forced close.

Run:
  uvicorn voice.server:app --port 8000 --reload
"""
from __future__ import annotations

import asyncio
import json
import logging
import struct
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types as gtypes

from src.agent import GEMINI_TOOL_DECLARATIONS, SYSTEM_PROMPT, _execute_tool
from src.config import GOOGLE_API_KEY, LIVE_MODEL


# Session lifecycle constants
IDLE_TIMEOUT_S = 60.0   # no real user speech for this long after agent finished → end session
HARD_LIMIT_S = 600.0    # absolute cap per session (10 min)
HEARTBEAT_S = 2.0       # how often the watchdog wakes
SPEECH_RMS_THRESHOLD = 0.005  # below this RMS, audio frame counts as silence (won't reset idle timer)


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("voice")


def _frame_is_speech(pcm16_bytes: bytes) -> bool:
    """Cheap VAD: compute RMS amplitude on a PCM16 frame; True if above threshold."""
    if not pcm16_bytes:
        return False
    n = len(pcm16_bytes) // 2
    if n == 0:
        return False
    samples = struct.unpack(f"<{n}h", pcm16_bytes)
    rms = (sum(s * s for s in samples) / n) ** 0.5 / 32768.0
    return rms > SPEECH_RMS_THRESHOLD


STATIC_DIR = Path(__file__).parent / "static"


app = FastAPI(title="3am Mom — voice")

# Serve the frontend at /
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "live_model": LIVE_MODEL, "key_set": bool(GOOGLE_API_KEY)}


def _live_config() -> gtypes.LiveConnectConfig:
    return gtypes.LiveConnectConfig(
        response_modalities=[gtypes.Modality.AUDIO],
        system_instruction=gtypes.Content(parts=[gtypes.Part(text=SYSTEM_PROMPT)]),
        tools=[gtypes.Tool(function_declarations=GEMINI_TOOL_DECLARATIONS)],
        input_audio_transcription=gtypes.AudioTranscriptionConfig(),
        output_audio_transcription=gtypes.AudioTranscriptionConfig(),
    )


@app.websocket("/ws")
async def voice_ws(ws: WebSocket) -> None:
    await ws.accept()

    if not GOOGLE_API_KEY:
        await ws.send_json({
            "type": "error",
            "message": "GOOGLE_API_KEY not set on the server",
        })
        await ws.close()
        return

    client = genai.Client(api_key=GOOGLE_API_KEY)
    session_started = time.time()
    # last_user_speech_ts only updates when an actual non-silent frame arrives
    # (so just streaming room noise doesn't keep the session alive forever, but a
    # user pausing to think doesn't kill it either).
    last_user_speech_ts = time.time()
    agent_speaking = False
    has_had_first_turn = False  # don't apply idle timeout until at least one exchange

    log.info("ws.open session_started=%.0f", session_started)

    async def watchdog():
        """End the session if no user speech for IDLE_TIMEOUT_S after the first
        exchange, or if HARD_LIMIT_S is reached. Never kills a session that hasn't
        had a single turn yet — the user might still be deciding what to say.
        """
        while True:
            await asyncio.sleep(HEARTBEAT_S)
            now = time.time()
            age = now - session_started
            silence_for = now - last_user_speech_ts

            if age > HARD_LIMIT_S:
                log.info("watchdog: hard_limit (age=%.0fs)", age)
                try:
                    await ws.send_json({"type": "session_ended", "reason": "hard_limit"})
                except Exception:
                    pass
                return "hard_limit"

            # Only enforce idle timeout once a real exchange has happened.
            if has_had_first_turn and silence_for > IDLE_TIMEOUT_S and not agent_speaking:
                log.info("watchdog: idle (silence_for=%.0fs)", silence_for)
                try:
                    await ws.send_json({"type": "session_ended", "reason": "idle"})
                except Exception:
                    pass
                return "idle"

    async with client.aio.live.connect(model=LIVE_MODEL, config=_live_config()) as session:
        await ws.send_json({"type": "session_started", "model": LIVE_MODEL})

        async def pump_browser_to_live():
            """Receive WS messages from the browser and forward to Live.

            Binary frames = PCM16 16kHz mono audio chunks.
            Text frames (JSON) = control messages (e.g. {"type": "stop"}).
            """
            nonlocal last_user_speech_ts
            try:
                while True:
                    msg = await ws.receive()
                    if msg.get("type") == "websocket.disconnect":
                        log.info("browser disconnected")
                        return "disconnect"
                    if "bytes" in msg and msg["bytes"] is not None:
                        chunk = msg["bytes"]
                        # Only treat above-threshold frames as "user speech" for
                        # idle-watchdog purposes. Forward all frames to Live so
                        # its server-side VAD has a continuous stream.
                        if _frame_is_speech(chunk):
                            last_user_speech_ts = time.time()
                        await session.send_realtime_input(
                            audio=gtypes.Blob(data=chunk, mime_type="audio/pcm;rate=16000"),
                        )
                    elif "text" in msg and msg["text"] is not None:
                        try:
                            payload = json.loads(msg["text"])
                        except json.JSONDecodeError:
                            continue
                        if payload.get("type") == "stop":
                            log.info("user_stop received")
                            return "user_stop"
                        if payload.get("type") == "text":
                            content = payload.get("content", "").strip()
                            if content:
                                last_user_speech_ts = time.time()
                                log.info("text turn: %r", content[:80])
                                await session.send_client_content(
                                    turns=[gtypes.Content(role="user", parts=[gtypes.Part(text=content)])],
                                    turn_complete=True,
                                )
            except WebSocketDisconnect:
                log.info("browser ws disconnected (exception)")
                return "disconnect"
            except Exception as e:
                log.exception("pump_browser_to_live error: %s", e)
                return "error"

        async def pump_live_to_browser():
            """Receive Live events and forward to the browser.

            Note: in this google-genai SDK version, `session.receive()` is a
            per-turn async generator — it ends when the model finishes a turn.
            To keep the Live session alive across multiple back-and-forth
            exchanges, we re-enter `session.receive()` in an outer loop until
            the session itself closes (no messages yielded) or an error fires.
            """
            nonlocal agent_speaking, has_had_first_turn
            try:
                turn_idx = 0
                while True:
                    got_any = False
                    async for message in session.receive():
                        got_any = True
                        if getattr(message, "tool_call", None):
                            for fc in message.tool_call.function_calls:
                                args = dict(fc.args or {})
                                log.info("tool_call: %s args=%s", fc.name, args)
                                await ws.send_json({"type": "tool_call", "name": fc.name, "args": args})
                                out = _execute_tool(fc.name, args)
                                ui_out = {"name": fc.name}
                                if fc.name == "escalation_check" and out.get("flag"):
                                    ui_out["flag"] = out["flag"]
                                elif fc.name == "knowledge_search":
                                    ui_out["chunk_ids"] = [c.get("chunk_id") for c in out.get("chunks", [])]
                                elif fc.name == "product_search":
                                    ui_out["products"] = [
                                        {
                                            "id": r["product"]["product_id"],
                                            "name_en": r["product"]["name_en"],
                                            "name_ar": r["product"]["name_ar"],
                                            "price_aed": r["product"]["price_aed"],
                                            "description_en": r["product"]["description_en"],
                                            "score": r.get("relevance_score"),
                                        }
                                        for r in out.get("recommendations", [])
                                    ]
                                await ws.send_json({"type": "tool_done", **ui_out})
                                await session.send_tool_response(function_responses=[
                                    gtypes.FunctionResponse(id=fc.id, name=fc.name, response=out),
                                ])
                        if getattr(message, "server_content", None):
                            sc = message.server_content
                            if getattr(sc, "input_transcription", None) and sc.input_transcription.text:
                                await ws.send_json({"type": "transcript_user", "text": sc.input_transcription.text})
                            if getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                                agent_speaking = True
                                await ws.send_json({"type": "transcript_agent", "text": sc.output_transcription.text})
                            if getattr(sc, "model_turn", None) and sc.model_turn.parts:
                                for p in sc.model_turn.parts:
                                    data = getattr(getattr(p, "inline_data", None), "data", None)
                                    if data:
                                        agent_speaking = True
                                        await ws.send_bytes(data)
                            if getattr(sc, "turn_complete", False):
                                agent_speaking = False
                                has_had_first_turn = True
                                log.info("turn_complete (turn %d) — re-entering receive()", turn_idx)
                                await ws.send_json({"type": "turn_complete"})
                    turn_idx += 1
                    if not got_any:
                        # receive() returned with no messages → session closed upstream
                        log.info("live receive() empty after turn %d, session closed", turn_idx)
                        return "live_closed"
                    # else: loop and call receive() again for the NEXT user turn
            except Exception as e:
                log.exception("pump_live_to_browser error: %s", e)
                return "error"

        # Race the three tasks; whichever finishes first ends the session.
        wd = asyncio.create_task(watchdog())
        b2l = asyncio.create_task(pump_browser_to_live())
        l2b = asyncio.create_task(pump_live_to_browser())

        done, pending = await asyncio.wait(
            {wd, b2l, l2b},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

    try:
        await ws.close()
    except Exception:
        pass
