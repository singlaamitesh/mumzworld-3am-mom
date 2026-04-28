"""3am Mom agent — text-mode entry point shared by Streamlit and the eval suite.

`Agent.turn(text)` runs against OpenRouter (free GPT-OSS-120B by default) with
three tools: NICE NG143 escalation regex, LanceDB knowledge_search, LanceDB
product_search. The voice surface (`voice/server.py`) reuses this module's
`SYSTEM_PROMPT`, `GEMINI_TOOL_DECLARATIONS`, and `_execute_tool` but drives the
Gemini Live session itself — this keeps the OpenAI-tool-format text path and
the Gemini-tool-format voice path cleanly separate.
"""
from __future__ import annotations
import json
from typing import Any

from openai import OpenAI

from src.config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, AGENT_MODEL, PROMPTS_DIR,
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

